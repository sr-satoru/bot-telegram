import os
import re
import logging
from functools import wraps
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Timezone de Brasília - compatível com Python 3.9+ e versões anteriores
try:
    from zoneinfo import ZoneInfo
    BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")
except ImportError:
    # Fallback para Python < 3.9 usando pytz
    try:
        import pytz
        BRASILIA_TZ = pytz.timezone("America/Sao_Paulo")
    except ImportError:
        # Se não tiver pytz, usa UTC-3 manualmente
        BRASILIA_TZ = timezone(timedelta(hours=-3))
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import Conflict
from db import prisma
from modules.criar_canal import (
    handle_criar_canal_callback, 
    handle_criar_canal_message,
    mostrar_menu_horarios,
    mostrar_menu_horarios_text,
    validar_horario
)
from bot_utils import is_super_admin, is_admin, require_admin, require_super_admin
from modules.edit.editar_nome import handle_edit_nome_callback, handle_edit_nome_message
from modules.edit.gerenciar_id import handle_edit_ids_callback, handle_edit_ids_message, mostrar_menu_ids
from modules.edit.gerenciar_time import handle_edit_time_callback, handle_edit_time_message, mostrar_menu_horarios_edicao
from modules.edit.gerenciar_template import handle_edit_template_callback, handle_edit_template_message, show_edit_panel
from modules.edit.gerenciar_midias import handle_edit_media_callback, handle_edit_media_input, mostrar_menu_medias, finalizar_grupo
from modules.edit.deletar_canal import handle_deletar_canal_callback
from db_helpers import (
    is_admin_db, add_admin, remove_admin, get_all_admins, get_admin,
    get_canal, get_all_canais, update_canal, get_template, get_templates_by_canal
)
from parser import MessageParser
from media_handler import MediaHandler
from scheduler import MediaScheduler
from setcomando import set_bot_commands

# Carrega variáveis de ambiente
load_dotenv()

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Token do bot (deve estar no arquivo .env)
BOT_TOKEN = os.getenv('BOT_TOKEN')

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN não encontrado no arquivo .env")

# ID do super admin (deve estar no arquivo .env)
SUPER_ADMIN = os.getenv('SUPER_ADMIN')

if not SUPER_ADMIN:
    raise ValueError("SUPER_ADMIN não encontrado no arquivo .env")

try:
    SUPER_ADMIN_ID = int(SUPER_ADMIN)
except ValueError:
    raise ValueError("SUPER_ADMIN deve ser um número inteiro válido")

parser = MessageParser()
media_handler = MediaHandler()

# Admin checks replaced by imports from bot_utils

@require_admin
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para o comando /start"""
    user_id = update.effective_user.id
    
    # Cancela qualquer fluxo em andamento
    keys_to_remove = [
        'criando_canal', 'criando_template', 'etapa', 'nome_canal', 'ids_canal', 
        'horarios', 'canal_id_template', 'pending_template', 'original_message',
        'links_received', 'current_link_index', 'use_same_link', 'waiting_for_link_choice'
    ]
    for key in keys_to_remove:
        context.user_data.pop(key, None)
    
    await mostrar_menu_inicial_msg(update.message, user_id)

async def mostrar_menu_inicial_query(query, user_id):
    """Versão do menu inicial para CallbackQuery"""
    keyboard = get_main_keyboard(user_id)
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "🤖 <b>Bot de Postagens canais</b>\n\nEscolha uma opção:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def mostrar_menu_inicial_msg(message, user_id):
    """Versão do menu inicial para Message"""
    keyboard = get_main_keyboard(user_id)
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text(
        "🤖 <b>Bot de Postagens canais</b>\n\nEscolha uma opção:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

def get_main_keyboard(user_id):
    """Gera o teclado principal baseado no nível de acesso"""
    keyboard = [
        [InlineKeyboardButton("📢 Criar Canal", callback_data="criar_canal")],
        [InlineKeyboardButton("✏️ Editar Canal", callback_data="editar_canal")]
    ]
    if is_super_admin(user_id):
        keyboard.append([InlineKeyboardButton("👥 Gerenciar Admins", callback_data="gerenciar_admins")])
        keyboard.append([InlineKeyboardButton("📊 Painel de Controle", callback_data="painel_controle")])
    return keyboard

@require_admin
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para processar callbacks dos botões inline"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    # Handlers do módulo Criar Canal
    res = await handle_criar_canal_callback(query, context)
    if res == "voltar_start":
        await mostrar_menu_inicial_query(query, user_id)
        return
    elif res:
        return

    if query.data == "editar_canal":
        # Lista os canais do usuário para editar
        user_id = query.from_user.id
        canais = await get_all_canais(user_id=user_id)
        
        if not canais:
            await query.edit_message_text(
                "📭 Nenhum canal encontrado.\n\nCrie um canal primeiro.",
                parse_mode='HTML'
            )
            return
        
        mensagem = "✏️ <b>Editar Canal</b>\n\nSelecione o canal para editar:"
        
        keyboard = []
        for canal in canais:
            nome = canal['nome']
            canal_id = canal['id']
            keyboard.append([
                InlineKeyboardButton(f"📢 {nome}", callback_data=f"editar_canal_{canal_id}")
            ])
        
        keyboard.append([
            InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_start"),
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    
    elif query.data == "voltar_start":
        # Volta para o menu inicial
        await mostrar_menu_inicial_query(query, user_id)
    
    # Template logic handled by modules.edit.gerenciar_template
    
    elif query.data.startswith("editar_canal_"):
        # Abre o menu de edição de um canal específico
        canal_id = int(query.data.split("_")[-1])
        user_id = query.from_user.id
        
        canal = await get_canal(canal_id)
        
        if not canal:
            await query.edit_message_text(
                "❌ Canal não encontrado.",
                parse_mode='HTML'
            )
            return
        
        # Verifica permissão: super admin pode editar qualquer canal, admin normal só os seus
        if not is_super_admin(user_id) and canal['user_id'] != user_id:
            await query.edit_message_text(
                "❌ Você não tem permissão para editar este canal.",
                parse_mode='HTML'
            )
            return
        
        # Salva dados do canal no contexto para edição
        context.user_data['editando'] = {
            'canal_id': canal_id,
            'nome': canal['nome'],
            'ids': canal['ids'].copy(),
            'horarios': canal['horarios'].copy(),
            'changes_made': False
        }
        
        await mostrar_menu_edicao(query, context)
    
    if await handle_edit_nome_callback(query, context):
        return
    
    if await handle_edit_ids_callback(query, context):
        return
        
    if await handle_edit_time_callback(query, context):
        return

    if await handle_edit_template_callback(query, context, parser):
        return

    if await handle_edit_media_callback(query, context, media_handler, prisma):
        return
    
    elif query.data == "edit_global_buttons":
        # Menu para gerenciar botões globais
        dados = context.user_data.get('editando', {})
        canal_id = dados.get('canal_id')
        
        if not canal_id:
            await query.edit_message_text("❌ Erro: canal não encontrado.", parse_mode='HTML')
            return
        
        global_buttons = await get_global_buttons(canal_id)
        
        mensagem = "🔘 <b>Botões Globais</b>\n\n"
        mensagem += "Botões globais são aplicados a TODOS os templates do canal.\n\n"
        
        if global_buttons:
            mensagem += f"<b>Botões configurados ({len(global_buttons)}):</b>\n"
            for i, button in enumerate(global_buttons, 1):
                url_display = button['url'] if len(button['url']) <= 40 else button['url'][:37] + "..."
                mensagem += f"{i}. '{button['text']}'\n   → {url_display}\n\n"
        else:
            mensagem += "❌ Nenhum botão global configurado\n\n"
        
        keyboard = []
        
        for button in global_buttons:
            button_display = button['text'][:25] + "..." if len(button['text']) > 25 else button['text']
            keyboard.append([
                InlineKeyboardButton(
                    f"✏️ {button_display}",
                    callback_data=f"edit_global_button_{button['id']}"
                ),
                InlineKeyboardButton(
                    f"🗑️",
                    callback_data=f"deletar_global_button_{button['id']}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("➕ Adicionar Botão Global", callback_data=f"adicionar_global_button_{canal_id}")
        ])
        
        keyboard.append([
            InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    
    elif query.data.startswith("adicionar_global_button_"):
        # Inicia adição de botão global
        canal_id = int(query.data.split("_")[-1])
        
        context.user_data['adicionando_global_button'] = True
        context.user_data['global_button_canal_id'] = canal_id
        context.user_data['global_button_etapa'] = 'texto'
        
        keyboard = [
            [
                InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_global_button"),
                InlineKeyboardButton("⬅️ Voltar", callback_data="edit_global_buttons")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "➕ <b>Adicionar Botão Global</b>\n\n"
            "Este botão será aplicado a TODOS os templates do canal.\n\n"
            "Envie o texto do botão:\n"
            "Ex: <code>Clique aqui</code>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif query.data.startswith("edit_global_button_"):
        # Edita um botão global
        button_id = int(query.data.split("_")[-1])
        
        # Busca informações do botão
        btn_info = await get_global_button_info(button_id)
        
        if not btn_info:
            await query.edit_message_text("❌ Botão não encontrado.", parse_mode='HTML')
            return
        
        canal_id, button_text, button_url, ordem = btn_info['canal_id'], btn_info['text'], btn_info['url'], btn_info['ordem']
        
        context.user_data['editando_global_button'] = True
        context.user_data['global_button_id'] = button_id
        context.user_data['global_button_canal_id'] = canal_id
        context.user_data['global_button_etapa'] = 'texto'
        
        url_display = button_url if len(button_url) <= 50 else button_url[:47] + "..."
        
        keyboard = [
            [
                InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_global_button"),
                InlineKeyboardButton("⬅️ Voltar", callback_data="edit_global_buttons")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✏️ <b>Editar Botão Global</b>\n\n"
            f"📝 Texto atual: '{button_text}'\n"
            f"🔗 URL atual: {url_display}\n\n"
            f"Envie o novo texto do botão:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif query.data.startswith("deletar_global_button_"):
        # Deleta um botão global
        button_id = int(query.data.split("_")[-1])
        
        # Busca canal_id antes de deletar
        btn_info = await get_global_button_info(button_id)
        
        if not btn_info:
            await query.edit_message_text("❌ Botão não encontrado.", parse_mode='HTML')
            return
        
        canal_id = btn_info['canal_id']
        
        deleted = await delete_global_button(button_id)
        
        if deleted:
            # Volta para o menu de botões globais
            global_buttons = await get_global_buttons(canal_id)
            
            mensagem = "✅ <b>Botão global deletado!</b>\n\n"
            mensagem += "🔘 <b>Botões Globais</b>\n\n"
            mensagem += "Botões globais são aplicados a TODOS os templates do canal.\n\n"
            
            if global_buttons:
                mensagem += f"<b>Botões configurados ({len(global_buttons)}):</b>\n"
                for i, button in enumerate(global_buttons, 1):
                    url_display = button['url'] if len(button['url']) <= 40 else button['url'][:37] + "..."
                    mensagem += f"{i}. '{button['text']}'\n   → {url_display}\n\n"
            else:
                mensagem += "❌ Nenhum botão global configurado\n\n"
            
            keyboard = []
            
            for button in global_buttons:
                button_display = button['text'][:25] + "..." if len(button['text']) > 25 else button['text']
                keyboard.append([
                    InlineKeyboardButton(
                        f"✏️ {button_display}",
                        callback_data=f"edit_global_button_{button['id']}"
                    ),
                    InlineKeyboardButton(
                        f"🗑️",
                        callback_data=f"deletar_global_button_{button['id']}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("➕ Adicionar Botão Global", callback_data=f"adicionar_global_button_{canal_id}")
            ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await query.edit_message_text("❌ Erro ao deletar botão.", parse_mode='HTML')
    
    elif query.data == "edit_salvar":
        # Salva as alterações
        dados = context.user_data.get('editando', {})
        
        if not dados or not dados.get('changes_made', False):
            await query.edit_message_text(
                "ℹ️ Nenhuma alteração para salvar.",
                parse_mode='HTML'
            )
            return
        
        try:
            await update_canal(
                canal_id=dados['canal_id'],
                nome=dados.get('nome'),
                ids_canal=dados.get('ids'),
                horarios=dados.get('horarios')
            )
            
            await query.edit_message_text(
                "✅ <b>Alterações salvas com sucesso!</b>",
                parse_mode='HTML'
            )
            
            # Limpa o contexto
            del context.user_data['editando']
            
        except Exception as e:
            logger.error(f"Erro ao salvar alterações: {e}")
            await query.edit_message_text(
                f"❌ Erro ao salvar: {str(e)}",
                parse_mode='HTML'
            )
    
    elif query.data == "edit_cancelar":
        # Cancela a edição
        if 'editando' in context.user_data:
            del context.user_data['editando']
        
        await query.edit_message_text(
            "❌ Edição cancelada.",
            parse_mode='HTML'
        )
    
    # Delegar para módulos de edição
    if await handle_edit_nome_callback(query, context):
        return
    if await handle_edit_ids_callback(query, context):
        return
    if await handle_edit_time_callback(query, context):
        return
    if await handle_edit_template_callback(query, context, parser):
        return
    if await handle_edit_media_callback(query, context, media_handler, prisma):
        return
    if await handle_deletar_canal_callback(query, context, mostrar_menu_edicao):
        return
    
    elif query.data == "confirmar_salvar_estatico":
        # Salva um template que não possui links (apenas formatação)
        template_data = context.user_data.get('pending_template')
        canal_id = context.user_data.get('canal_id_template')
        
        if not template_data or not canal_id:
            await query.answer("❌ Erro ao recuperar dados do template.")
            return

        template_id = await save_template(
            canal_id=canal_id,
            template_mensagem=template_data['template_mensagem'],
            links=[]
        )
        
        # Limpa contexto
        for key in ['criando_template', 'etapa', 'canal_id_template', 'pending_template', 'original_message']:
            context.user_data.pop(key, None)
            
        keyboard = [[InlineKeyboardButton("✅ Finalizar", callback_data="voltar_start")]]
        await query.edit_message_text(
            f"✅ <b>Template estático salvo!</b>\n\n"
            f"📝 ID: {template_id}\n"
            f"⚠️ Este template não possui links dinâmicos.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    
    elif query.data == "link_choice_keep":
        # Salva o template usando os links originais que vieram na mensagem
        template_data = context.user_data.get('pending_template')
        canal_id = context.user_data.get('canal_id_template')
        links_originais = context.user_data.get('links_received', [])
        
        if not template_data or not canal_id:
            await query.answer("❌ Erro ao recuperar dados do template.")
            return
            
        # Constrói a lista de tuplas (segmento, url)
        links_list = []
        for i, url in enumerate(links_originais):
            link_text = template_data['segmentos'][i]
            links_list.append((link_text, url))
            
        template_id = await save_template(
            canal_id=canal_id,
            template_mensagem=template_data['template_mensagem'],
            links=links_list
        )
        
        # Limpa contexto
        for key in ['criando_template', 'etapa', 'canal_id_template', 'pending_template', 
                   'original_message', 'links_received', 'current_link_index']:
            context.user_data.pop(key, None)
            
        keyboard = [[InlineKeyboardButton("✅ Finalizar", callback_data="voltar_start")]]
        await query.edit_message_text(
            f"✅ <b>Template salvo com links originais!</b>\n\n"
            f"📝 ID: {template_id}\n"
            f"🔗 Links salvos: {len(links_list)}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    
    elif query.data == "link_choice_same":
        # Usar o mesmo link para todos
        context.user_data['use_same_link'] = True
        context.user_data['waiting_for_link_choice'] = False
        context.user_data['etapa'] = 'recebendo_link'
        context.user_data['links_received'] = [] # Limpa os links detectados anteriormente
        
        template_data = context.user_data['pending_template']
        num_links = template_data['num_links']
        
        await query.edit_message_text(
            f"✅ <b>Mesmo link para todos</b>\n\n"
            f"Envie o URL do link:\n"
            f"Exemplo: <code>https://example.com</code>",
            parse_mode='HTML'
        )
    
    elif query.data == "link_choice_separate":
        # Usar links separados
        context.user_data['use_same_link'] = False
        context.user_data['waiting_for_link_choice'] = False
        context.user_data['etapa'] = 'recebendo_link'
        context.user_data['links_received'] = [] # Limpa os links detectados anteriormente
        
        template_data = context.user_data['pending_template']
        segmentos = template_data['segmentos']
        num_links = template_data['num_links']
        
        await query.edit_message_text(
            f"✅ <b>Links separados</b>\n\n"
            f"Envie o URL do primeiro link (1/{num_links}):\n"
            f"Segmento: '{segmentos[0]}'\n"
            f"Exemplo: <code>https://example.com</code>",
            parse_mode='HTML'
        )
    
    # Template and Media callbacks handled by modules
    
    # Template and Media callbacks handled by modules
    
    elif query.data.startswith("adicionar_template_"):
        # Inicia criação de novo template para o canal
        canal_id = int(query.data.split("_")[-1])
        context.user_data['criando_template'] = True
        context.user_data['canal_id_template'] = canal_id
        context.user_data['etapa'] = 'template_mensagem'
        
        await query.edit_message_text(
            "📝 <b>Adicionar Template</b>\n\n"
            "Envie a mensagem usando a formatação do Telegram:\n"
            "• Use <b>negrito</b>, <i>itálico</i>, <u>sublinhado</u>, etc.\n"
            "• Use <b>Inserir Link</b> (hiperlink) no próprio texto.\n\n"
            "O bot identificará todos os links e a formatação automaticamente! ✅",
            parse_mode='HTML'
        )
    
    elif query.data.startswith("deletar_template_"):
        # Confirmação para deletar template
        template_id = int(query.data.split("_")[-1])
        template = await get_template(template_id)
        
        if not template:
            await query.edit_message_text("❌ Template não encontrado.", parse_mode='HTML')
            return
        
        template_msg = template['template_mensagem']
        preview = template_msg[:40] + "..." if len(template_msg) > 40 else template_msg
        
        mensagem = f"🗑️ <b>Deletar Template?</b>\n\n"
        mensagem += f"📝 ID: {template_id}\n"
        mensagem += f"📄 {preview}\n\n"
        mensagem += "⚠️ Esta ação não pode ser desfeita!"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data=f"confirmar_deletar_template_{template_id}"),
                InlineKeyboardButton("❌ Cancelar", callback_data="edit_templates")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    
    elif query.data.startswith("confirmar_deletar_template_"):
        # Deleta o template
        template_id = int(query.data.split("_")[-1])
        
        deleted = await delete_template(template_id)
        
        if deleted:
            # Volta para a lista de templates
            dados = context.user_data.get('editando', {})
            canal_id = dados.get('canal_id')
            
            if canal_id:
                templates = await get_templates_by_canal(canal_id)
                
                mensagem = f"✅ <b>Template deletado!</b>\n\n"
                mensagem += f"📝 <b>Gerenciar Templates</b>\n\n"
                mensagem += f"Total: {len(templates)} template(s)\n\n"
                
                keyboard = []
                for template in templates:
                    template_id_item = template['id']
                    template_msg = template['template_mensagem']
                    preview = template_msg[:25] + "..." if len(template_msg) > 25 else template_msg
                    keyboard.append([
                        InlineKeyboardButton(f"📄 {preview}", callback_data=f"edit_template_{template_id_item}"),
                        InlineKeyboardButton("👁️ Preview", callback_data=f"preview_template_{template_id_item}")
                    ])
                    keyboard.append([
                        InlineKeyboardButton("🗑️ Deletar", callback_data=f"deletar_template_{template_id_item}")
                    ])
                
                keyboard.append([
                    InlineKeyboardButton("➕ Adicionar Template", callback_data=f"adicionar_template_{canal_id}")
                ])
                
                keyboard.append([
                    InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar")
                ])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
            else:
                await query.edit_message_text("✅ Template deletado!", parse_mode='HTML')
        else:
            await query.edit_message_text("❌ Erro ao deletar template.", parse_mode='HTML')
    
    elif query.data.startswith("edit_template_"):
        # Mostra painel de edição de links do template
        template_id = int(query.data.split("_")[-1])
        await show_edit_panel(query, template_id, context)
    
    elif query.data.startswith("mudar_link_geral_canal_"):
        # Mostra painel com opções de mudança de link para TODOS os templates do canal
        canal_id = int(query.data.split("_")[-1])
        
        # Verifica quantos templates existem
        templates = await get_templates_by_canal(canal_id)
        num_templates = len(templates)
        
        mensagem = "🔄 <b>Mudar Link Geral do Canal</b>\n\n"
        mensagem += f"⚠️ Esta ação afetará <b>TODOS os {num_templates} template(s)</b> do canal.\n\n"
        mensagem += "Escolha como os links devem ser alterados:\n"
        mensagem += "• <b>Link global:</b> altera todos os links de todos os templates.\n"
        mensagem += "• <b>Link de bot:</b> altera apenas links de bots do Telegram, mantendo parâmetros como ?start.\n"
        mensagem += "• <b>Link externo:</b> altera apenas links que não sejam do Telegram.\n\n"
        
        keyboard = [
            [InlineKeyboardButton("🌐 Link global", callback_data=f"mudar_link_global_canal_{canal_id}")],
            [InlineKeyboardButton("🤖 Link de bot", callback_data=f"mudar_link_bot_canal_{canal_id}")],
            [InlineKeyboardButton("🔗 Link externo", callback_data=f"mudar_link_externo_canal_{canal_id}")],
            [InlineKeyboardButton("⬅️ Voltar", callback_data="edit_templates")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    
    elif query.data.startswith("mudar_link_global_canal_"):
        # Substitui TODOS os links de TODOS os templates do canal
        canal_id = int(query.data.split("_")[-1])
        templates = await get_templates_by_canal(canal_id)
        
        if not templates:
            await query.edit_message_text("❌ Nenhum template encontrado.", parse_mode='HTML')
            return
        
        # Salva contexto
        context.user_data['mudando_link_global_canal'] = True
        context.user_data['mudando_link_canal_id'] = canal_id
        
        await query.edit_message_text(
            "🌐 <b>Link Global do Canal</b>\n\n"
            f"📝 Canal ID: {canal_id}\n"
            f"📄 Templates: {len(templates)}\n\n"
            "Envie o novo link que substituirá TODOS os links de TODOS os templates:\n"
            "Ex: <code>https://t.me/meubot</code>",
            parse_mode='HTML'
        )
    
    elif query.data.startswith("mudar_link_bot_canal_"):
        # Substitui apenas links de bot do Telegram de TODOS os templates
        canal_id = int(query.data.split("_")[-1])
        templates = await get_templates_by_canal(canal_id)
        
        if not templates:
            await query.edit_message_text("❌ Nenhum template encontrado.", parse_mode='HTML')
            return
        
        # Salva contexto
        context.user_data['mudando_link_bot_canal'] = True
        context.user_data['mudando_link_canal_id'] = canal_id
        
        await query.edit_message_text(
            "🤖 <b>Link de Bot do Canal</b>\n\n"
            f"📝 Canal ID: {canal_id}\n"
            f"📄 Templates: {len(templates)}\n\n"
            "Envie o novo link do bot do Telegram:\n"
            "Ex: <code>https://t.me/meubot</code>\n\n"
            "⚠️ Apenas links de bots do Telegram serão alterados em todos os templates.\n"
            "Links com parâmetros (?start=) terão apenas o bot alterado.",
            parse_mode='HTML'
        )
    
    elif query.data.startswith("mudar_link_externo_canal_"):
        # Substitui apenas links externos (não Telegram) de TODOS os templates
        canal_id = int(query.data.split("_")[-1])
        templates = await get_templates_by_canal(canal_id)
        
        if not templates:
            await query.edit_message_text("❌ Nenhum template encontrado.", parse_mode='HTML')
            return
        
        # Salva contexto
        context.user_data['mudando_link_externo_canal'] = True
        context.user_data['mudando_link_canal_id'] = canal_id
        
        await query.edit_message_text(
            "🔗 <b>Link Externo do Canal</b>\n\n"
            f"📝 Canal ID: {canal_id}\n"
            f"📄 Templates: {len(templates)}\n\n"
            "Envie o novo link que substituirá os links externos em todos os templates:\n"
            "Ex: <code>https://example.com</code>\n\n"
            "⚠️ Apenas links que NÃO sejam do Telegram serão alterados.",
            parse_mode='HTML'
        )
    
    elif query.data == "edit_cancel":
        # Cancela edição de links
        await query.edit_message_text("❌ Edição cancelada.", parse_mode='HTML')
        return
    
    elif query.data == "cancelar_global_button":
        # Cancela adição/edição de botão global
        dados = context.user_data.get('editando', {})
        canal_id = dados.get('canal_id')
        
        # Limpa contexto de botão global
        for key in ['adicionando_global_button', 'global_button_canal_id', 
                   'global_button_etapa', 'global_button_text',
                   'editando_global_button', 'global_button_id', 
                   'global_button_new_text']:
            context.user_data.pop(key, None)
        
        if canal_id:
            # Volta para o menu de botões globais
            global_buttons = await get_global_buttons(canal_id)
            
            mensagem = "❌ <b>Operação cancelada</b>\n\n"
            mensagem += "🔘 <b>Botões Globais</b>\n\n"
            mensagem += "Botões globais são aplicados a TODOS os templates do canal.\n\n"
            
            if global_buttons:
                mensagem += f"<b>Botões configurados ({len(global_buttons)}):</b>\n"
                for i, button in enumerate(global_buttons, 1):
                    url_display = button['url'] if len(button['url']) <= 40 else button['url'][:37] + "..."
                    mensagem += f"{i}. '{button['text']}'\n   → {url_display}\n\n"
            else:
                mensagem += "❌ Nenhum botão global configurado\n\n"
            
            keyboard = []
            
            for button in global_buttons:
                button_display = button['text'][:25] + "..." if len(button['text']) > 25 else button['text']
                keyboard.append([
                    InlineKeyboardButton(
                        f"✏️ {button_display}",
                        callback_data=f"edit_global_button_{button['id']}"
                    ),
                    InlineKeyboardButton(
                        f"🗑️",
                        callback_data=f"deletar_global_button_{button['id']}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("➕ Adicionar Botão Global", callback_data=f"adicionar_global_button_{canal_id}")
            ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await query.edit_message_text("❌ Operação cancelada.", parse_mode='HTML')
        return
    
    elif query.data.startswith("edit_all_"):
        # Edita todos os links do template
        template_id = int(query.data.split("_")[-1])
        template = await get_template_with_link_ids(template_id)
        
        if not template:
            await query.edit_message_text("❌ Template não encontrado.", parse_mode='HTML')
            return
        
        num_links = len(template['links'])
        
        # Salva contexto para edição de todos
        context.user_data['editing_all_links'] = True
        context.user_data['editing_template_id'] = template_id
        context.user_data['editing_num_links'] = num_links
        
        await query.edit_message_text(
            f"🔗 <b>Editando todos os links</b>\n\n"
            f"📝 Template ID: {template_id}\n"
            f"🔗 Total: {num_links} segmento(s)\n\n"
            f"Envie o URL para TODOS os segmentos:\n"
            f"Ex: <code>https://example.com</code>",
            parse_mode='HTML'
        )
        return
    
    elif query.data.startswith("adicionar_inline_button_"):
        # Inicia adição de botão inline
        template_id = int(query.data.split("_")[-1])
        
        context.user_data['adicionando_inline_button'] = True
        context.user_data['inline_button_template_id'] = template_id
        context.user_data['inline_button_etapa'] = 'texto'
        
        await query.edit_message_text(
            "➕ <b>Adicionar Botão Inline</b>\n\n"
            "Envie o texto do botão:\n"
            "Ex: <code>Clique aqui</code>",
            parse_mode='HTML'
        )
    
    elif query.data.startswith("edit_inline_button_"):
        # Edita um botão inline
        button_id = int(query.data.split("_")[-1])
        
        # Busca informações do botão
        btn_info = await get_inline_button_info(button_id)
        
        if not btn_info:
            await query.edit_message_text("❌ Botão não encontrado.", parse_mode='HTML')
            return
        
        template_id, button_text, button_url, ordem = btn_info['template_id'], btn_info['text'], btn_info['url'], btn_info['ordem']
        
        context.user_data['editando_inline_button'] = True
        context.user_data['inline_button_id'] = button_id
        context.user_data['inline_button_template_id'] = template_id
        context.user_data['inline_button_etapa'] = 'texto'
        
        url_display = button_url if len(button_url) <= 50 else button_url[:47] + "..."
        await query.edit_message_text(
            f"✏️ <b>Editar Botão Inline</b>\n\n"
            f"📝 Texto atual: '{button_text}'\n"
            f"🔗 URL atual: {url_display}\n\n"
            f"Envie o novo texto do botão:",
            parse_mode='HTML'
        )
    
    elif query.data.startswith("deletar_inline_button_"):
        # Deleta um botão inline
        button_id = int(query.data.split("_")[-1])
        
        # Busca template_id antes de deletar
        btn_info = await get_inline_button_info(button_id)
        
        if not btn_info:
            await query.edit_message_text("❌ Botão não encontrado.", parse_mode='HTML')
            return
        
        template_id = btn_info['template_id']
        
        deleted = await delete_inline_button(button_id)
        
        if deleted:
            await show_edit_panel(query, template_id, context, "✅ Botão inline deletado!")
        else:
            await query.edit_message_text("❌ Erro ao deletar botão.", parse_mode='HTML')
    
    elif query.data.startswith("edit_link_"):
        # Edita um link específico
        link_id = int(query.data.split("_")[-1])
        link_info = await get_link_info(link_id)
        
        if not link_info:
            await query.edit_message_text("❌ Link não encontrado.", parse_mode='HTML')
            return
        
        link_id_db, template_id, segmento, url_atual, ordem = link_info
        
        # Salva contexto para edição
        context.user_data['editing_link_id'] = link_id
        context.user_data['editing_template_id'] = template_id
        context.user_data['editing_segmento'] = segmento
        context.user_data['editing_ordem'] = ordem
        
        url_display = url_atual if len(url_atual) <= 50 else url_atual[:47] + "..."
        await query.edit_message_text(
            f"✏️ <b>Editando segmento {ordem}</b>\n\n"
            f"📝 Segmento: '{segmento}'\n"
            f"🔗 URL atual: {url_display}\n\n"
            f"Envie o novo URL:\n"
            f"Ex: <code>https://example.com</code>",
            parse_mode='HTML'
        )
    
    elif query.data == "edit_medias":
        # Menu para gerenciar mídias
        await mostrar_menu_medias(query, context)
    
    elif query.data == "salvar_midia_unica":
        # Inicia fluxo para salvar mídia única
        dados = context.user_data.get('editando', {})
        canal_id = dados.get('canal_id')
        
        if not canal_id:
            await query.edit_message_text("❌ Erro: canal não encontrado.", parse_mode='HTML')
            return
        
        context.user_data['salvando_midia'] = True
        context.user_data['tipo_midia'] = 'unica'
        context.user_data['canal_id_midia'] = canal_id
        
        keyboard = [
            [InlineKeyboardButton("❌ Cancelar", callback_data="edit_medias")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📸 <b>Salvar Mídia Única</b>\n\n"
            "Envie uma foto ou vídeo para salvar.\n\n"
            "A mídia será armazenada usando file_id (sem salvar no servidor).",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif query.data == "salvar_midia_agrupada":
        # Inicia fluxo para salvar mídia agrupada
        dados = context.user_data.get('editando', {})
        canal_id = dados.get('canal_id')
        
        if not canal_id:
            await query.edit_message_text("❌ Erro: canal não encontrado.", parse_mode='HTML')
            return
        
        context.user_data['salvando_midia'] = True
        context.user_data['tipo_midia'] = 'agrupada'
        context.user_data['canal_id_midia'] = canal_id
        context.user_data['medias_temporarias'] = []
        context.user_data['criando_grupo'] = False
        
        keyboard = [
            [InlineKeyboardButton("❌ Cancelar", callback_data="edit_medias")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📦 <b>Salvar Mídia Agrupada</b>\n\n"
            "Envie múltiplas fotos ou vídeos (até 10).\n\n"
            "Envie as mídias uma por vez. Quando terminar, use /finalizar_grupo",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif query.data.startswith("ver_grupo_midia_"):
        # Mostra detalhes de um grupo de mídias
        group_id = int(query.data.split("_")[-1])
        await mostrar_detalhes_grupo_midia(query, context, group_id)
    
    elif query.data.startswith("deletar_grupo_midia_"):
        # Confirma deleção de grupo de mídias
        group_id = int(query.data.split("_")[-1])
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data=f"confirmar_deletar_grupo_{group_id}"),
                InlineKeyboardButton("❌ Cancelar", callback_data="edit_medias")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚠️ <b>Confirmar Deleção</b>\n\n"
            f"Tem certeza que deseja deletar este grupo de mídias?",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif query.data.startswith("confirmar_deletar_grupo_"):
        # Deleta grupo de mídias
        group_id = int(query.data.split("_")[-1])
        
        deleted = await delete_media_group(group_id)
        
        if deleted:
            await query.edit_message_text(
                "✅ Grupo de mídias deletado com sucesso!",
                parse_mode='HTML'
            )
            await mostrar_menu_medias(query, context)
        else:
            await query.edit_message_text(
                "❌ Erro ao deletar grupo de mídias.",
                parse_mode='HTML'
            )
    
    elif query.data.startswith("preview_grupo_midia_"):
        # Mostra preview do grupo de mídias com template e botões
        group_id = int(query.data.split("_")[-1])
        await enviar_preview_grupo_midia(query, context, group_id)
    
    elif query.data.startswith("associar_template_grupo_"):
        # Inicia associação de template ao grupo de mídias
        group_id = int(query.data.split("_")[-1])
        
        # Busca templates do canal
        dados = context.user_data.get('editando', {})
        canal_id = dados.get('canal_id')
        
        if not canal_id:
            await query.edit_message_text("❌ Erro: canal não encontrado.", parse_mode='HTML')
            return
        
        templates = await get_templates_by_canal(canal_id)
        
        if not templates:
            await query.edit_message_text(
                "❌ Nenhum template encontrado neste canal.\n\n"
                "Crie um template primeiro em 'Gerenciar Templates'.",
                parse_mode='HTML'
            )
            return
        
        mensagem = "📝 <b>Associar Template</b>\n\n"
        mensagem += "Selecione o template para associar ao grupo de mídias:"
        
        keyboard = []
        for template in templates:
            preview = template['template_mensagem'][:30] + "..." if len(template['template_mensagem']) > 30 else template['template_mensagem']
            keyboard.append([
                InlineKeyboardButton(
                    f"📄 {preview}",
                    callback_data=f"confirmar_associar_template_{group_id}_{template['id']}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("⬅️ Voltar", callback_data=f"ver_grupo_midia_{group_id}")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    
    elif query.data.startswith("confirmar_associar_template_"):
        # Confirma associação de template ao grupo
        parts = query.data.split("_")
        group_id = int(parts[-2])
        template_id = int(parts[-1])
        
        # Atualiza o grupo de mídias
        await update_media_group(group_id, template_id=template_id)
        
        await query.edit_message_text(
            f"✅ Template associado com sucesso!",
            parse_mode='HTML'
        )
        
        # Volta para os detalhes do grupo
        await mostrar_detalhes_grupo_midia(query, context, group_id)
    
    elif query.data.startswith("remover_template_grupo_"):
        # Remove template do grupo de mídias
        group_id = int(query.data.split("_")[-1])
        
        # Atualiza o grupo removendo o template
        success = await update_media_group(group_id, remove_template=True)
        
        if success:
            await query.answer("✅ Template removido!")
            await mostrar_detalhes_grupo_midia(query, context, group_id)
        else:
            await query.answer("❌ Erro ao remover template", show_alert=True)
    
    elif query.data == "associar_template_automatico":
        # Associa template automaticamente a todos os grupos sem template
        dados = context.user_data.get('editando', {})
        canal_id = dados.get('canal_id')
        user_id = query.from_user.id
        
        if not canal_id:
            await query.edit_message_text("❌ Erro: canal não encontrado.", parse_mode='HTML')
            return
        
        # Busca templates do canal
        templates = await get_templates_by_canal(canal_id)
        
        if not templates:
            await query.edit_message_text(
                "❌ Nenhum template encontrado neste canal.\n\n"
                "Crie um template primeiro em 'Gerenciar Templates'.",
                parse_mode='HTML'
            )
            return
        
        # Se houver apenas um template, associa automaticamente
        if len(templates) == 1:
            template_id = templates[0]['id']
            # Busca grupos sem template
            media_groups = await get_media_groups_by_user(user_id, canal_id)
            grupos_sem_template = [g for g in media_groups if not g.get('template_id')]
            
            if not grupos_sem_template:
                await query.edit_message_text(
                    "✅ Todos os grupos já têm template associado!",
                    parse_mode='HTML'
                )
                return
            
            # Associa template a todos os grupos sem template
            for group in grupos_sem_template:
                await update_media_group(group['id'], template_id=template_id)
            
            await query.edit_message_text(
                f"✅ Template associado automaticamente a {len(grupos_sem_template)} grupo(s)!",
                parse_mode='HTML'
            )
            await mostrar_menu_medias(query, context)
        else:
            # Se houver múltiplos templates, pergunta qual usar
            mensagem = "📝 <b>Associar Template Automaticamente</b>\n\n"
            mensagem += "Selecione o template para associar a todos os grupos sem template:"
            
            keyboard = []
            for template in templates:
                preview = template['template_mensagem'][:30] + "..." if len(template['template_mensagem']) > 30 else template['template_mensagem']
                keyboard.append([
                    InlineKeyboardButton(
                        f"📄 {preview}",
                        callback_data=f"confirmar_associar_auto_{template['id']}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Voltar", callback_data="edit_medias")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    
    elif query.data.startswith("confirmar_associar_auto_"):
        # Confirma associação automática de template
        template_id = int(query.data.split("_")[-1])
        dados = context.user_data.get('editando', {})
        canal_id = dados.get('canal_id')
        user_id = query.from_user.id
        
        # Busca grupos sem template
        media_groups = await get_media_groups_by_user(user_id, canal_id)
        grupos_sem_template = [g for g in media_groups if not g.get('template_id')]
        
        if not grupos_sem_template:
            await query.edit_message_text(
                "✅ Todos os grupos já têm template associado!",
                parse_mode='HTML'
            )
            return
        
        # Associa template a todos os grupos sem template
        for group in grupos_sem_template:
            await update_media_group(group['id'], template_id=template_id)
        
        await query.edit_message_text(
            f"✅ Template associado automaticamente a {len(grupos_sem_template)} grupo(s)!",
            parse_mode='HTML'
        )
        await mostrar_menu_medias(query, context)
    

    elif query.data == "listar_grupos_midias":
        # Lista todos os grupos de mídias
        dados = context.user_data.get('editando', {})
        canal_id = dados.get('canal_id')
        user_id = query.from_user.id
        
        media_groups = await get_media_groups_by_user(user_id, canal_id)
        
        if not media_groups:
            await query.edit_message_text(
                "❌ Nenhum grupo de mídias encontrado.",
                parse_mode='HTML'
            )
            return
        
        mensagem = "📦 <b>Grupos de Mídias</b>\n\n"
        
        keyboard = []
        for group in media_groups:
            nome = group['nome']
            group_id = group['id']
            count = group.get('media_count', 0)
            
            display = f"📦 {nome} ({count})"
            if len(display) > 40:
                display = display[:37] + "..."
            
            keyboard.append([
                InlineKeyboardButton(display, callback_data=f"ver_grupo_midia_{group_id}")
            ])
        
        keyboard.append([
            InlineKeyboardButton("⬅️ Voltar", callback_data="edit_medias")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    
    elif query.data == "edit_voltar":
        # Volta para o menu de edição
        await mostrar_menu_edicao(query, context)
    
    
    elif query.data == "gerenciar_admins":
        # Apenas super admin pode acessar
        if not is_super_admin(query.from_user.id):
            await query.answer("❌ Apenas o super admin pode gerenciar admins.", show_alert=True)
            return
        
        admins = await get_all_admins()
        
        mensagem = "👥 <b>Gerenciar Admins</b>\n\n"
        
        if not admins:
            mensagem += "Nenhum admin cadastrado."
        else:
            mensagem += "Admins cadastrados:\n\n"
            for admin in admins:
                username = admin['username'] or 'Sem username'
                admin_id = admin['user_id']
                mensagem += f"• ID: <code>{admin_id}</code> - @{username}\n"
        
        keyboard = [
            [InlineKeyboardButton("➕ Adicionar Admin", callback_data="adicionar_admin")],
            [InlineKeyboardButton("➖ Remover Admin", callback_data="remover_admin_lista")],
            [InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    
    elif query.data == "adicionar_admin":
        # Apenas super admin pode adicionar
        if not is_super_admin(query.from_user.id):
            await query.answer("❌ Apenas o super admin pode adicionar admins.", show_alert=True)
            return
        
        context.user_data['adicionando_admin'] = True
        
        await query.edit_message_text(
            "➕ <b>Adicionar Admin</b>\n\n"
            "Envie o ID do usuário que deseja adicionar como admin:",
            parse_mode='HTML'
        )
    
    elif query.data == "remover_admin_lista":
        # Apenas super admin pode remover
        if not is_super_admin(query.from_user.id):
            await query.answer("❌ Apenas o super admin pode remover admins.", show_alert=True)
            return
        
        admins = await get_all_admins()
        
        if not admins:
            await query.answer("❌ Nenhum admin cadastrado.", show_alert=True)
            return
        
        mensagem = "➖ <b>Remover Admin</b>\n\nSelecione o admin para remover:"
        
        keyboard = []
        for admin in admins:
            username = admin['username'] or 'Sem username'
            admin_id = admin['user_id']
            keyboard.append([
                InlineKeyboardButton(
                    f"❌ {username} ({admin_id})",
                    callback_data=f"remover_admin_{admin_id}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data="gerenciar_admins")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    
    elif query.data.startswith("remover_admin_"):
        # Apenas super admin pode remover
        if not is_super_admin(query.from_user.id):
            await query.answer("❌ Apenas o super admin pode remover admins.", show_alert=True)
            return
        
        admin_id = int(query.data.split("_")[-1])
        
        # Não permite remover o super admin
        if admin_id == SUPER_ADMIN_ID:
            await query.answer("❌ Não é possível remover o super admin.", show_alert=True)
            return
        
        removed = await remove_admin(admin_id)
        
        if removed:
            await query.answer("✅ Admin removido com sucesso!", show_alert=True)
            # Recarrega a lista
            await handle_callback(update, context)
        else:
            await query.answer("❌ Erro ao remover admin.", show_alert=True)
    
    elif query.data == "painel_controle":
        # Apenas super admin pode acessar
        if not is_super_admin(query.from_user.id):
            await query.answer("❌ Apenas o super admin pode acessar o painel de controle.", show_alert=True)
            return
        
        admins = await get_all_admins()
        
        mensagem = "📊 <b>Painel de Controle</b>\n\n"
        mensagem += "📈 <b>Visão Geral</b>\n\n"
        
        # Estatísticas gerais
        all_canais = await get_all_canais()
        total_canais = len(all_canais)
        
        mensagem += f"📢 Total de Canais: {total_canais}\n"
        mensagem += f"👥 Total de Admins: {len(admins)}\n\n"
        
        # Canais por admin
        if admins:
            mensagem += "📋 <b>Canais por Admin:</b>\n\n"
            for admin in admins:
                admin_id = admin['user_id']
                username = admin['username'] or f"ID {admin_id}"
                admin_canais = await get_all_canais(user_id=admin_id)
                mensagem += f"👤 @{username} ({admin_id}): {len(admin_canais)} canal(is)\n"
        
        keyboard = []
        if admins:
            for admin in admins:
                admin_id = admin['user_id']
                username = admin['username'] or f"ID {admin_id}"
                keyboard.append([
                    InlineKeyboardButton(
                        f"📊 Ver Canais de @{username}",
                        callback_data=f"ver_canais_admin_{admin_id}"
                    )
                ])
        
        keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_start")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    
    elif query.data.startswith("ver_canais_admin_"):
        # Apenas super admin pode ver
        if not is_super_admin(query.from_user.id):
            await query.answer("❌ Apenas o super admin pode ver isso.", show_alert=True)
            return
        
        admin_id = int(query.data.split("_")[-1])
        admin_info = await get_admin(admin_id)
        
        if not admin_info:
            await query.answer("❌ Admin não encontrado.", show_alert=True)
            return
        
        username = admin_info['username'] or f"ID {admin_id}"
        canais = await get_all_canais(user_id=admin_id)
        
        mensagem = f"📊 <b>Canais de @{username}</b>\n\n"
        
        if not canais:
            mensagem += "Nenhum canal cadastrado."
        else:
            for canal in canais:
                mensagem += f"📢 <b>{canal['nome']}</b> (ID: {canal['id']})\n"
                mensagem += f"   • Canais: {len(canal['ids'])}\n"
                mensagem += f"   • Horários: {len(canal['horarios'])}\n\n"
        
        keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="painel_controle")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    

@require_admin
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Orquestrador de mídia que delega para os módulos"""
    if await handle_edit_media_input(update, context, media_handler):
        return

@require_admin
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para mensagens de texto e legendas"""
    # Captura o texto ou legenda com HTML para preservar formatação e links
    message_html = ""
    if update.message.text_html:
        message_html = update.message.text_html
    elif update.message.caption_html:
        message_html = update.message.caption_html
    else:
        message_html = update.message.text or update.message.caption or ""
        
    message_text = update.message.text or update.message.caption or ""
    user_id = update.message.from_user.id
    
    # Verifica se está adicionando admin
    if context.user_data.get('adicionando_admin', False):
        if not is_super_admin(user_id):
            context.user_data.pop('adicionando_admin', None)
            await update.message.reply_text("❌ Você não tem permissão para adicionar admins.")
            return
        
        try:
            admin_id = int(message_text.strip())
            
            # Não permite adicionar o super admin como admin
            if admin_id == SUPER_ADMIN_ID:
                await update.message.reply_text("❌ O super admin já tem todas as permissões.")
                context.user_data.pop('adicionando_admin', None)
                return
            
            # Tenta obter username do usuário
            try:
                from telegram import Bot
                bot = context.bot
                user_info = await bot.get_chat(admin_id)
                username = user_info.username
            except:
                username = None
            
            # Adiciona admin
            success = await add_admin(admin_id, username)
            
            if success:
                context.user_data.pop('adicionando_admin', None)
                await update.message.reply_text(
                    f"✅ <b>Admin adicionado com sucesso!</b>\n\n"
                    f"ID: <code>{admin_id}</code> - @{username if username else 'Sem username'}\n\n"
                    f"O usuário agora pode usar o bot.",
                    parse_mode='HTML'
                )
            else:
                await update.message.reply_text(
                    f"⚠️ Este usuário já é admin ou ocorreu um erro ao adicionar."
                )
        except ValueError:
            await update.message.reply_text(
                "❌ ID inválido. Por favor, envie apenas números (exemplo: 123456789)."
            )
        return
    
    # Verifica se está finalizando grupo de mídias
    if context.user_data.get('criando_grupo', False):
        # Esta parte não deve ser mais alcançada pois o nome é gerado automaticamente
        # Mantendo apenas para limpeza de contexto caso algo dê errado
        for key in ['salvando_midia', 'tipo_midia', 'canal_id_midia', 
                   'medias_temporarias', 'criando_grupo', 'etapa_grupo']:
            context.user_data.pop(key, None)
        return

    
    # Template creation handled by modules.edit.gerenciar_template
    
    # Verifica se está editando um canal
    if 'editando' in context.user_data:
        dados = context.user_data['editando']
        etapa = dados.get('etapa')
        
        if await handle_edit_nome_message(update, context):
            return
        
        if await handle_edit_ids_message(update, context):
            return
            
        if await handle_edit_time_message(update, context):
            return
    
    # Handlers do módulo Criar Canal
    if await handle_criar_canal_message(update, context):
        return

    if await handle_edit_template_message(update, context, parser):
        return

    if await handle_edit_media_input(update, context, media_handler):
        return
        
    # Global/Inline buttons and links handled by modules


async def mostrar_menu_edicao(query, context):
    """Mostra o menu principal de edição"""
    dados = context.user_data.get('editando', {})
    
    if not dados:
        await query.edit_message_text("❌ Erro: dados de edição não encontrados.", parse_mode='HTML')
        return
    
    mensagem = f"🔧 <b>Menu de Edição</b>\n\n"
    mensagem += f"📢 <b>Nome:</b> {dados['nome']}\n"
    mensagem += f"🆔 <b>IDs:</b> {len(dados['ids'])} ID(s)\n"
    mensagem += f"🕒 <b>Horários:</b> {len(dados['horarios'])} horário(s)\n\n"
    mensagem += "Escolha o que deseja editar:"
    
    keyboard = [
        [
            InlineKeyboardButton("📛 Editar Nome", callback_data="edit_nome"),
        ],
        [
            InlineKeyboardButton("🆔 Gerenciar IDs", callback_data="edit_ids"),
        ],
        [
            InlineKeyboardButton("🕒 Gerenciar Horários", callback_data="edit_horarios_menu"),
        ],
        [
            InlineKeyboardButton("📝 Gerenciar Templates", callback_data="edit_templates"),
        ],
        [
            InlineKeyboardButton("🔘 Botões Globais", callback_data="edit_global_buttons"),
        ],
        [
            InlineKeyboardButton("📸 Gerenciar Mídias", callback_data="edit_medias"),
        ],
        [
            InlineKeyboardButton("🗑️ Deletar Canal", callback_data="edit_deletar_canal"),
        ],
    ]
    
    if dados.get('changes_made', False):
        keyboard.append([
            InlineKeyboardButton("✅ Salvar Alterações", callback_data="edit_salvar"),
        ])
    
    keyboard.append([
        InlineKeyboardButton("⬅️ Voltar", callback_data="editar_canal"),
        InlineKeyboardButton("✖️ Cancelar", callback_data="edit_cancelar"),
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')



    # Helper functions handled by modules

# Variável global para o scheduler
scheduler = None

async def post_init(application: Application) -> None:
    """Inicializa o scheduler após o bot estar pronto"""
    global scheduler

    # Conecta ao banco de dados Prisma
    await prisma.connect()
    
    # Define os comandos do bot
    await set_bot_commands(application)
    
    # Aguarda um pouco para garantir que o bot está totalmente inicializado
    import asyncio
    await asyncio.sleep(2)
    
    scheduler = MediaScheduler(media_handler, application.bot)
    
    # Inicia o scheduler em background
    asyncio.create_task(scheduler.run_scheduler())
    logger.info("🚀 Scheduler de mídias iniciado!")

async def post_shutdown(application: Application) -> None:
    """Desconecta o cliente Prisma ao encerrar o bot"""
    await prisma.disconnect()
    logger.info("🔌 Prisma desconectado.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Trata erros que ocorrem durante o processamento de updates"""
    # Trata erros de conflito (múltiplas instâncias) de forma silenciosa
    if isinstance(context.error, Conflict):
        # Log apenas em nível DEBUG para não poluir os logs
        logger.debug(f"Conflito de polling detectado (normal quando há múltiplas instâncias): {context.error}")
        return
    
    # Para outros erros, loga normalmente
    logger.error(f"Erro não tratado: {context.error}", exc_info=context.error)

def main():
    """Função principal para iniciar o bot"""
    # Cria a aplicação
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()
    
    # Adiciona error handler para tratar conflitos de forma silenciosa
    application.add_error_handler(error_handler)
    
    # Adiciona handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("finalizar_grupo", finalizar_grupo))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    # Handler para mídias (fotos e vídeos)
    # Nota: Documentos enviados como arquivo não são capturados automaticamente
    # O usuário deve enviar fotos/vídeos diretamente (não como arquivo)
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_media))
    
    # Inicia o bot com polling apenas
    # drop_pending_updates=True garante que ignora updates pendentes e deleta webhook se houver
    logger.info("Bot de Postagens canais iniciado! (Modo: Polling apenas)")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True  # Deleta webhook e ignora updates pendentes
    )

if __name__ == '__main__':
    main()

