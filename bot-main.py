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
from database import Database
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

# Inicializa banco de dados, parser e media handler
db = Database()
parser = MessageParser()
media_handler = MediaHandler(db)

def is_super_admin(user_id: int) -> bool:
    """Verifica se o usuário é o super admin"""
    return user_id == SUPER_ADMIN_ID

def is_admin(user_id: int) -> bool:
    """Verifica se o usuário é admin (super admin ou admin normal)"""
    if is_super_admin(user_id):
        return True
    return db.is_admin(user_id)

def is_admin_only(user_id: int) -> bool:
    """Verifica se o usuário é apenas admin (não super admin)"""
    return db.is_admin(user_id) and not is_super_admin(user_id)

def require_admin(func):
    """Decorador que verifica se o usuário é admin ou super admin antes de executar a função"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        if not is_admin(user_id):
            message_text = "❌ Você não tem permissão para usar este bot. Fale com o @sr_satoru_Gojo para liberrar seu acesso "
            try:
                if update.callback_query:
                    await update.callback_query.answer(message_text, show_alert=True)
                elif update.message:
                    await update.message.reply_text(message_text)
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem de permissão: {e}")
            return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper

def require_super_admin(func):
    """Decorador que verifica se o usuário é super admin antes de executar a função"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        if not is_super_admin(user_id):
            message_text = "❌ Você não tem permissão para usar este bot."
            try:
                if update.callback_query:
                    await update.callback_query.answer(message_text, show_alert=True)
                elif update.message:
                    await update.message.reply_text(message_text)
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem de permissão: {e}")
            return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper

@require_admin
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para o comando /start"""
    user_id = update.effective_user.id
    
    # Cancela qualquer fluxo de cadastro em andamento
    keys_to_remove = [
        'criando_canal',
        'criando_template',
        'etapa',
        'nome_canal',
        'ids_canal',
        'horarios',
        'canal_id_template',
        'pending_template',
        'original_message',
        'links_received',
        'current_link_index',
        'use_same_link',
        'waiting_for_link_choice',
        'adicionando_inline_button',
        'inline_button_template_id',
        'inline_button_etapa',
        'inline_button_text',
        'editando_inline_button',
        'inline_button_id',
        'inline_button_new_text',
        'adicionando_global_button',
        'global_button_canal_id',
        'global_button_etapa',
        'global_button_text',
        'editando_global_button',
        'global_button_id',
        'global_button_new_text',
        'editing_all_links',
        'editing_template_id',
        'editing_num_links',
        'editing_link_id',
        'editing_segmento',
        'editing_ordem',
        'editando',
        'adicionando_admin',
        'admin_user_id'
    ]
    
    for key in keys_to_remove:
        context.user_data.pop(key, None)
    
    welcome_message = "🤖 <b>Bot de Postagens canais</b>\n\nEscolha uma opção:"
    
    # Cria botões inline
    keyboard = [
        [
            InlineKeyboardButton("📢 Criar Canal", callback_data="criar_canal"),
        ],
        [
            InlineKeyboardButton("✏️ Editar Canal", callback_data="editar_canal"),
        ]
    ]
    
    # Super admin vê opção de gerenciar admins
    if is_super_admin(user_id):
        keyboard.append([
            InlineKeyboardButton("👥 Gerenciar Admins", callback_data="gerenciar_admins")
        ])
        keyboard.append([
            InlineKeyboardButton("📊 Painel de Controle", callback_data="painel_controle")
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

@require_admin
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para processar callbacks dos botões inline"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "criar_canal":
        # Inicia o fluxo de criação de canal
        context.user_data['criando_canal'] = True
        context.user_data['etapa'] = 'nome'
        
        await query.edit_message_text(
            "📢 <b>Criar Canal</b>\n\nEnvie o nome:",
            parse_mode='HTML'
        )
    
    elif query.data == "editar_canal":
        # Lista os canais do usuário para editar
        user_id = query.from_user.id
        canais = db.get_all_canais(user_id=user_id)
        
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
        user_id = query.from_user.id
        welcome_message = "🤖 <b>Bot de Postagens canais</b>\n\nEscolha uma opção:"
        
        keyboard = [
            [
                InlineKeyboardButton("📢 Criar Canal", callback_data="criar_canal"),
            ],
            [
                InlineKeyboardButton("✏️ Editar Canal", callback_data="editar_canal"),
            ]
        ]
        
        # Super admin vê opção de gerenciar admins
        if is_super_admin(user_id):
            keyboard.append([
                InlineKeyboardButton("👥 Gerenciar Admins", callback_data="gerenciar_admins")
            ])
            keyboard.append([
                InlineKeyboardButton("📊 Painel de Controle", callback_data="painel_controle")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            welcome_message,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif query.data.startswith("criar_template_"):
        # Inicia criação de template para um canal
        user_id = query.from_user.id
        canal_id = int(query.data.split("_")[-1])
        
        # Verifica se o canal pertence ao admin (isolamento)
        canal = db.get_canal(canal_id)
        if not canal:
            await query.answer("❌ Canal não encontrado.", show_alert=True)
            return
        
        if not is_super_admin(user_id) and canal['user_id'] != user_id:
            await query.answer("❌ Você não tem permissão para criar templates neste canal.", show_alert=True)
            return
        
        context.user_data['criando_template'] = True
        context.user_data['canal_id_template'] = canal_id
        context.user_data['etapa'] = 'template_mensagem'
        
        await query.edit_message_text(
            "📝 <b>Criar Template</b>\n\n"
            "Envie a mensagem com variáveis de link:\n"
            "Formato: <code>{link = texto}</code>\n\n"
            "Exemplo:\n"
            "<code>Olá {link = clique aqui} tudo certo {link = me responde}</code>",
            parse_mode='HTML'
        )
    
    elif query.data.startswith("editar_canal_"):
        # Abre o menu de edição de um canal específico
        canal_id = int(query.data.split("_")[-1])
        user_id = query.from_user.id
        
        canal = db.get_canal(canal_id)
        
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
    
    elif query.data == "edit_nome":
        # Inicia edição do nome
        context.user_data['editando']['etapa'] = 'editando_nome'
        
        await query.edit_message_text(
            f"📛 <b>Editar Nome</b>\n\nNome atual: <b>{context.user_data['editando']['nome']}</b>\n\nEnvie o novo nome:",
            parse_mode='HTML'
        )
    
    elif query.data == "edit_ids":
        # Menu para gerenciar IDs
        await mostrar_menu_ids(query, context)
    
    elif query.data == "edit_horarios_menu":
        # Menu para gerenciar horários
        await mostrar_menu_horarios_edicao(query, context)
    
    elif query.data == "edit_global_buttons":
        # Menu para gerenciar botões globais
        dados = context.user_data.get('editando', {})
        canal_id = dados.get('canal_id')
        
        if not canal_id:
            await query.edit_message_text("❌ Erro: canal não encontrado.", parse_mode='HTML')
            return
        
        global_buttons = db.get_global_buttons(canal_id)
        
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
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT canal_id, button_text, button_url, ordem FROM canal_global_buttons WHERE id = ?', (button_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            await query.edit_message_text("❌ Botão não encontrado.", parse_mode='HTML')
            return
        
        canal_id, button_text, button_url, ordem = result
        
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
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT canal_id FROM canal_global_buttons WHERE id = ?', (button_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            await query.edit_message_text("❌ Botão não encontrado.", parse_mode='HTML')
            return
        
        canal_id = result[0]
        
        deleted = db.delete_global_button(button_id)
        
        if deleted:
            # Volta para o menu de botões globais
            global_buttons = db.get_global_buttons(canal_id)
            
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
            db.update_canal(
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
    
    elif query.data == "edit_deletar_canal":
        # Confirmação para deletar canal
        user_id = query.from_user.id
        dados = context.user_data.get('editando', {})
        
        if not dados:
            await query.answer("❌ Erro: dados não encontrados.", show_alert=True)
            return
        
        canal_id = dados.get('canal_id')
        nome_canal = dados.get('nome', 'Canal')
        
        # Verifica permissão
        canal = db.get_canal(canal_id)
        if not canal:
            await query.answer("❌ Canal não encontrado.", show_alert=True)
            return
        
        if not is_super_admin(user_id) and canal['user_id'] != user_id:
            await query.answer("❌ Você não tem permissão para deletar este canal.", show_alert=True)
            return
        
        # Mostra confirmação
        mensagem = f"⚠️ <b>Confirmar Exclusão</b>\n\n"
        mensagem += f"Tem certeza que deseja <b>DELETAR</b> o canal:\n\n"
        mensagem += f"📢 <b>{nome_canal}</b>\n\n"
        mensagem += f"<b>Esta ação não pode ser desfeita!</b>\n\n"
        mensagem += f"❌ Serão deletados:\n"
        mensagem += f"• Canal e configurações\n"
        mensagem += f"• Todos os templates\n"
        mensagem += f"• Todos os grupos de mídias\n"
        mensagem += f"• Todas as configurações relacionadas\n"
        
        keyboard = [
            [
                InlineKeyboardButton("❌ Confirmar Deletar", callback_data=f"confirmar_deletar_canal_{canal_id}"),
            ],
            [
                InlineKeyboardButton("⬅️ Cancelar", callback_data="cancelar_deletar_canal"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    
    elif query.data.startswith("confirmar_deletar_canal_"):
        # Confirma e deleta o canal
        user_id = query.from_user.id
        canal_id = int(query.data.split("_")[-1])
        
        # Verifica permissão novamente
        canal = db.get_canal(canal_id)
        if not canal:
            await query.answer("❌ Canal não encontrado.", show_alert=True)
            return
        
        if not is_super_admin(user_id) and canal['user_id'] != user_id:
            await query.answer("❌ Você não tem permissão para deletar este canal.", show_alert=True)
            return
        
        nome_canal = canal['nome']
        
        # Deleta o canal
        deleted = db.delete_canal(canal_id)
        
        if deleted:
            # Limpa contexto de edição
            if 'editando' in context.user_data:
                del context.user_data['editando']
            
            # Mensagem de sucesso com botão para voltar ao menu
            keyboard = [
                [
                    InlineKeyboardButton("⬅️ Voltar ao Menu", callback_data="voltar_start"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"✅ <b>Canal deletado com sucesso!</b>\n\n"
                f"📢 <b>{nome_canal}</b> foi permanentemente removido.\n\n"
                f"Todos os dados relacionados foram excluídos.",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await query.answer("❌ Erro ao deletar canal.", show_alert=True)
    
    elif query.data == "cancelar_deletar_canal":
        # Cancela a deleção e volta para o menu de edição
        await mostrar_menu_edicao(query, context)
    
    elif query.data == "link_choice_same":
        # Usar o mesmo link para todos
        context.user_data['use_same_link'] = True
        context.user_data['waiting_for_link_choice'] = False
        context.user_data['etapa'] = 'recebendo_link'
        
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
    
    elif query.data == "edit_templates":
        # Lista templates do canal
        dados = context.user_data.get('editando', {})
        canal_id = dados.get('canal_id')
        
        if not canal_id:
            await query.edit_message_text("❌ Erro: canal não encontrado.", parse_mode='HTML')
            return
        
        templates = db.get_templates_by_canal(canal_id)
        
        if not templates:
            keyboard = [
                [InlineKeyboardButton("➕ Adicionar Template", callback_data=f"adicionar_template_{canal_id}")],
                [InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "📝 <b>Gerenciar Templates</b>\n\n❌ Nenhum template encontrado.",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            return
        
        mensagem = f"📝 <b>Gerenciar Templates</b>\n\n"
        mensagem += f"Total: {len(templates)} template(s)\n\n"
        
        keyboard = []
        for template in templates:
            template_id = template['id']
            template_msg = template['template_mensagem']
            preview = template_msg[:25] + "..." if len(template_msg) > 25 else template_msg
            keyboard.append([
                InlineKeyboardButton(f"📄 {preview}", callback_data=f"edit_template_{template_id}"),
                InlineKeyboardButton("👁️ Preview", callback_data=f"preview_template_{template_id}")
            ])
            keyboard.append([
                InlineKeyboardButton("🗑️ Deletar", callback_data=f"deletar_template_{template_id}")
            ])
        
        keyboard.append([
            InlineKeyboardButton("➕ Adicionar Template", callback_data=f"adicionar_template_{canal_id}")
        ])
        
        keyboard.append([
            InlineKeyboardButton("🔗 Mudar link geral", callback_data=f"mudar_link_geral_canal_{canal_id}")
        ])
        
        keyboard.append([
            InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    
    elif query.data.startswith("preview_template_"):
        # Mostra preview do template formatado
        template_id = int(query.data.split("_")[-1])
        template = db.get_template(template_id)
        
        if not template:
            await query.edit_message_text("❌ Template não encontrado.", parse_mode='HTML')
            return
        
        template_mensagem = template['template_mensagem']
        links = template['links']  # Lista de dicionários com 'segmento' e 'link'
        inline_buttons = template.get('inline_buttons', [])
        canal_id = template.get('canal_id')
        
        # Busca botões globais do canal
        global_buttons = []
        if canal_id:
            global_buttons = db.get_global_buttons(canal_id)
        
        # Converte para formato de tuplas (segmento, link_url)
        links_tuples = [(link['segmento'], link['link']) for link in links]
        
        # Formata a mensagem com links HTML
        formatted_message = parser.format_message_with_links(template_mensagem, links_tuples)
        
        # Monta mensagem com informações
        preview_text = f"👁️ <b>Preview - Template ID: {template_id}</b>\n\n"
        preview_text += f"📄 <b>Mensagem formatada:</b>\n\n"
        preview_text += formatted_message
        
        # Cria botões inline para preview (globais + individuais)
        preview_keyboard = []
        all_buttons = []
        
        # Adiciona botões globais primeiro
        if global_buttons:
            preview_text += f"\n\n🔘 <b>Botões Globais ({len(global_buttons)}):</b>\n"
            for button in global_buttons:
                preview_text += f"• 🌐 {button['text']} → {button['url'][:30]}...\n"
                all_buttons.append(InlineKeyboardButton(button['text'], url=button['url']))
        
        # Adiciona botões individuais do template
        if inline_buttons:
            preview_text += f"\n🔘 <b>Botões do Template ({len(inline_buttons)}):</b>\n"
            for button in inline_buttons:
                preview_text += f"• {button['text']} → {button['url'][:30]}...\n"
                all_buttons.append(InlineKeyboardButton(button['text'], url=button['url']))
        
        # Organiza botões em linhas (2 por linha)
        if all_buttons:
            button_row = []
            for button in all_buttons:
                button_row.append(button)
                if len(button_row) >= 2:
                    preview_keyboard.append(button_row)
                    button_row = []
            if button_row:
                preview_keyboard.append(button_row)
        
        # Botões de navegação
        nav_buttons = [
            InlineKeyboardButton("⬅️ Voltar", callback_data="edit_templates"),
            InlineKeyboardButton("✏️ Editar", callback_data=f"edit_template_{template_id}")
        ]
        preview_keyboard.append(nav_buttons)
        
        reply_markup = InlineKeyboardMarkup(preview_keyboard)
        
        await query.edit_message_text(preview_text, reply_markup=reply_markup, parse_mode='HTML')
    
    elif query.data.startswith("adicionar_template_"):
        # Inicia criação de novo template para o canal
        canal_id = int(query.data.split("_")[-1])
        context.user_data['criando_template'] = True
        context.user_data['canal_id_template'] = canal_id
        context.user_data['etapa'] = 'template_mensagem'
        
        await query.edit_message_text(
            "📝 <b>Adicionar Template</b>\n\n"
            "Envie a mensagem com variáveis de link:\n"
            "Formato: <code>{link = texto}</code>\n\n"
            "Exemplo:\n"
            "<code>Olá {link = clique aqui} tudo certo {link = me responde}</code>",
            parse_mode='HTML'
        )
    
    elif query.data.startswith("deletar_template_"):
        # Confirmação para deletar template
        template_id = int(query.data.split("_")[-1])
        template = db.get_template(template_id)
        
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
        
        deleted = db.delete_template(template_id)
        
        if deleted:
            # Volta para a lista de templates
            dados = context.user_data.get('editando', {})
            canal_id = dados.get('canal_id')
            
            if canal_id:
                templates = db.get_templates_by_canal(canal_id)
                
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
        templates = db.get_templates_by_canal(canal_id)
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
        templates = db.get_templates_by_canal(canal_id)
        
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
        templates = db.get_templates_by_canal(canal_id)
        
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
        templates = db.get_templates_by_canal(canal_id)
        
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
            global_buttons = db.get_global_buttons(canal_id)
            
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
        template = db.get_template_with_link_ids(template_id)
        
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
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT template_id, button_text, button_url, ordem FROM template_inline_buttons WHERE id = ?', (button_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            await query.edit_message_text("❌ Botão não encontrado.", parse_mode='HTML')
            return
        
        template_id, button_text, button_url, ordem = result
        
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
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT template_id FROM template_inline_buttons WHERE id = ?', (button_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            await query.edit_message_text("❌ Botão não encontrado.", parse_mode='HTML')
            return
        
        template_id = result[0]
        
        deleted = db.delete_inline_button(button_id)
        
        if deleted:
            await show_edit_panel(query, template_id, context, "✅ Botão inline deletado!")
        else:
            await query.edit_message_text("❌ Erro ao deletar botão.", parse_mode='HTML')
    
    elif query.data.startswith("edit_link_"):
        # Edita um link específico
        link_id = int(query.data.split("_")[-1])
        link_info = db.get_link_info(link_id)
        
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
        
        deleted = db.delete_media_group(group_id)
        
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
        
        templates = db.get_templates_by_canal(canal_id)
        
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
        db.update_media_group(group_id, template_id=template_id)
        
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
        success = db.update_media_group(group_id, remove_template=True)
        
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
        templates = db.get_templates_by_canal(canal_id)
        
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
            media_groups = db.get_media_groups_by_user(user_id, canal_id)
            grupos_sem_template = [g for g in media_groups if not g.get('template_id')]
            
            if not grupos_sem_template:
                await query.edit_message_text(
                    "✅ Todos os grupos já têm template associado!",
                    parse_mode='HTML'
                )
                return
            
            # Associa template a todos os grupos sem template
            for group in grupos_sem_template:
                db.update_media_group(group['id'], template_id=template_id)
            
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
        media_groups = db.get_media_groups_by_user(user_id, canal_id)
        grupos_sem_template = [g for g in media_groups if not g.get('template_id')]
        
        if not grupos_sem_template:
            await query.edit_message_text(
                "✅ Todos os grupos já têm template associado!",
                parse_mode='HTML'
            )
            return
        
        # Associa template a todos os grupos sem template
        for group in grupos_sem_template:
            db.update_media_group(group['id'], template_id=template_id)
        
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
        
        media_groups = db.get_media_groups_by_user(user_id, canal_id)
        
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
    
    elif query.data == "edit_add_id":
        # Inicia adição de ID
        context.user_data['editando']['etapa'] = 'adicionando_id'
        
        keyboard = [
            [
                InlineKeyboardButton("❌ Cancelar", callback_data="edit_voltar"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🆔 <b>Adicionar ID</b>\n\nEnvie o ID do Telegram do canal:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif query.data == "edit_remove_id":
        # Mostra lista de IDs para remover
        dados = context.user_data.get('editando', {})
        ids = dados.get('ids', [])
        
        if not ids:
            await query.edit_message_text(
                "⚠️ Nenhum ID para remover.",
                parse_mode='HTML'
            )
            return
        
        keyboard = []
        for i, canal_id in enumerate(ids):
            keyboard.append([
                InlineKeyboardButton(f"❌ {canal_id}", callback_data=f"edit_remove_id_{i}")
            ])
        
        keyboard.append([
            InlineKeyboardButton("⬅️ Voltar", callback_data="edit_ids"),
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🗑 <b>Remover ID</b>\n\nSelecione o ID para remover:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif query.data.startswith("edit_remove_id_"):
        # Remove um ID específico
        index = int(query.data.split("_")[-1])
        dados = context.user_data.get('editando', {})
        ids = dados.get('ids', [])
        
        if 0 <= index < len(ids):
            id_removido = ids.pop(index)
            dados['ids'] = ids
            dados['changes_made'] = True
            
            await mostrar_menu_ids(query, context)
    
    elif query.data == "edit_add_horario":
        # Inicia adição de horário
        context.user_data['editando']['etapa'] = 'adicionando_horario'
        
        keyboard = [
            [
                InlineKeyboardButton("❌ Cancelar", callback_data="edit_horarios_menu"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🕒 <b>Adicionar Horário</b>\n\nEnvie os horários (formato 24h, separados por vírgula):\nEx: <code>08:00, 12:30</code>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif query.data == "edit_remove_horario":
        # Mostra lista de horários para remover
        dados = context.user_data.get('editando', {})
        horarios = dados.get('horarios', [])
        
        if not horarios:
            await query.edit_message_text(
                "⚠️ Nenhum horário para remover.",
                parse_mode='HTML'
            )
            return
        
        keyboard = []
        horarios_ordenados = sorted(horarios)
        for i, horario in enumerate(horarios_ordenados):
            keyboard.append([
                InlineKeyboardButton(f"❌ {horario}", callback_data=f"edit_remove_horario_{i}")
            ])
        
        keyboard.append([
            InlineKeyboardButton("⬅️ Voltar", callback_data="edit_horarios_menu"),
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🗑 <b>Remover Horário</b>\n\nSelecione o horário para remover:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif query.data.startswith("edit_remove_horario_"):
        # Remove um horário específico
        index = int(query.data.split("_")[-1])
        dados = context.user_data.get('editando', {})
        horarios = dados.get('horarios', [])
        horarios_ordenados = sorted(horarios)
        
        if 0 <= index < len(horarios_ordenados):
            horario_removido = horarios_ordenados[index]
            horarios.remove(horario_removido)
            dados['horarios'] = horarios
            dados['changes_made'] = True
            
            await mostrar_menu_horarios_edicao(query, context)
    
    elif query.data == "adicionar_outro_id":
        # Adiciona outro ID para o mesmo canal
        context.user_data['etapa'] = 'id'
        
        keyboard = [
            [
                InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_adicionar_id"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📢 <b>Adicionar outro ID</b>\n\nEnvie outro ID do Telegram:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif query.data == "cancelar_adicionar_id":
        # Volta para a etapa de confirmar (mostra a mensagem com IDs e botões)
        nome_canal = context.user_data.get('nome_canal', 'N/A')
        ids_canal = context.user_data.get('ids_canal', [])
        
        if not ids_canal:
            await query.edit_message_text(
                "⚠️ Nenhum ID adicionado.",
                parse_mode='HTML'
            )
            return
        
        # Monta mensagem com lista de IDs
        total_ids = len(ids_canal)
        mensagem = f"✅ <b>Canal adicionado!</b>\n\n"
        mensagem += f"📢 {nome_canal}\n\n"
        mensagem += f"<b>IDs ({total_ids}):</b>\n"
        
        for i, canal_id in enumerate(ids_canal, 1):
            mensagem += f"{i}. <code>{canal_id}</code>\n"
        
        # Cria botões
        keyboard = [
            [
                InlineKeyboardButton("➕ Adicionar outro ID", callback_data="adicionar_outro_id"),
            ],
            [
                InlineKeyboardButton("✅ Confirmar", callback_data="confirmar_canal"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    
    elif query.data == "confirmar_canal":
        # Confirma os IDs e vai para etapa de horários
        nome_canal = context.user_data.get('nome_canal', 'N/A')
        ids_canal = context.user_data.get('ids_canal', [])
        
        if not ids_canal:
            await query.edit_message_text(
                "⚠️ Nenhum ID adicionado.",
                parse_mode='HTML'
            )
            return
        
        # Inicializa horários
        context.user_data['horarios'] = []
        context.user_data['etapa'] = 'horarios'
        
        mensagem = f"✅ <b>Canal confirmado!</b>\n\n"
        mensagem += f"📢 {nome_canal}\n"
        mensagem += f"🆔 IDs ({len(ids_canal)}):\n"
        for i, canal_id in enumerate(ids_canal, 1):
            mensagem += f"{i}. <code>{canal_id}</code>\n"
        mensagem += "\n🕒 <b>Adicionar Horários</b>\n\n"
        mensagem += "Envie os horários no formato 24h, separados por vírgula.\n"
        mensagem += "Exemplo: <code>08:00, 12:30, 18:00, 22:15</code>"
        
        keyboard = [
            [
                InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_horarios"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    
    elif query.data == "cancelar_horarios":
        # Cancela a etapa de horários
        del context.user_data['criando_canal']
        del context.user_data['etapa']
        del context.user_data['horarios']
        
        await query.edit_message_text(
            "❌ Adição de horários cancelada.",
            parse_mode='HTML'
        )
    
    elif query.data == "adicionar_horario":
        # Adiciona mais horários
        context.user_data['etapa'] = 'horarios'
        
        keyboard = [
            [
                InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_adicionar_horario"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🕒 <b>Adicionar Horário</b>\n\nEnvie os horários (formato 24h, separados por vírgula):\nEx: <code>08:00, 12:30</code>",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif query.data == "cancelar_adicionar_horario":
        # Volta para o menu de horários
        await mostrar_menu_horarios(query, context)
    
    elif query.data == "remover_horario":
        # Mostra lista de horários para remover
        horarios = context.user_data.get('horarios', [])
        
        if not horarios:
            await query.edit_message_text(
                "⚠️ Nenhum horário para remover.",
                parse_mode='HTML'
            )
            return
        
        keyboard = []
        horarios_ordenados = sorted(horarios)
        for i, horario in enumerate(horarios_ordenados):
            keyboard.append([
                InlineKeyboardButton(f"❌ {horario}", callback_data=f"remove_horario_{i}")
            ])
        
        keyboard.append([
            InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_menu_horarios"),
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        mensagem = "🗑 <b>Remover Horário</b>\n\nSelecione o horário para remover:"
        
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    
    elif query.data.startswith("remove_horario_"):
        # Remove um horário específico
        index = int(query.data.split("_")[-1])
        horarios = context.user_data.get('horarios', [])
        horarios_ordenados = sorted(horarios)
        
        if 0 <= index < len(horarios_ordenados):
            horario_removido = horarios_ordenados[index]
            context.user_data['horarios'].remove(horario_removido)
            
            await mostrar_menu_horarios(query, context)
    
    elif query.data == "voltar_menu_horarios":
        # Volta para o menu de horários
        await mostrar_menu_horarios(query, context)
    
    elif query.data == "confirmar_horarios":
        # Confirma os horários e salva no banco de dados
        horarios = context.user_data.get('horarios', [])
        nome_canal = context.user_data.get('nome_canal', 'N/A')
        ids_canal = context.user_data.get('ids_canal', [])
        user_id = query.from_user.id
        
        if not horarios:
            await query.edit_message_text(
                "⚠️ Nenhum horário adicionado.",
                parse_mode='HTML'
            )
            return
        
        # Salva no banco de dados
        try:
            canal_id = db.save_canal(
                nome=nome_canal,
                ids_canal=ids_canal,
                horarios=horarios,
                user_id=user_id
            )
            
            mensagem = f"✅ <b>Canal salvo!</b>\n\n"
            mensagem += f"📢 {nome_canal}\n"
            mensagem += f"🆔 IDs ({len(ids_canal)}):\n"
            for i, canal_id_telegram in enumerate(ids_canal, 1):
                mensagem += f"{i}. <code>{canal_id_telegram}</code>\n"
            mensagem += f"\n🕒 Horários ({len(horarios)}):\n"
            for i, horario in enumerate(sorted(horarios), 1):
                mensagem += f"{i}. {horario}\n"
            mensagem += f"\n💾 ID: {canal_id}\n\n"
            
            keyboard = [
                [
                    InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_start"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
        except Exception as e:
            logger.error(f"Erro ao salvar canal: {e}")
            mensagem = f"❌ Erro: {str(e)}"
            reply_markup = None
        
        # Limpa o contexto
        del context.user_data['criando_canal']
        del context.user_data['etapa']
        del context.user_data['nome_canal']
        del context.user_data['ids_canal']
        del context.user_data['horarios']
        
        if reply_markup:
            await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
        else:
            await query.edit_message_text(mensagem, parse_mode='HTML')
    
    elif query.data == "gerenciar_admins":
        # Apenas super admin pode acessar
        if not is_super_admin(query.from_user.id):
            await query.answer("❌ Apenas o super admin pode gerenciar admins.", show_alert=True)
            return
        
        admins = db.get_all_admins()
        
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
        
        admins = db.get_all_admins()
        
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
        
        removed = db.remove_admin(admin_id)
        
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
        
        admins = db.get_all_admins()
        
        mensagem = "📊 <b>Painel de Controle</b>\n\n"
        mensagem += "📈 <b>Visão Geral</b>\n\n"
        
        # Estatísticas gerais
        all_canais = db.get_all_canais()
        total_canais = len(all_canais)
        
        mensagem += f"📢 Total de Canais: {total_canais}\n"
        mensagem += f"👥 Total de Admins: {len(admins)}\n\n"
        
        # Canais por admin
        if admins:
            mensagem += "📋 <b>Canais por Admin:</b>\n\n"
            for admin in admins:
                admin_id = admin['user_id']
                username = admin['username'] or f"ID {admin_id}"
                admin_canais = db.get_all_canais(user_id=admin_id)
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
        admin_info = db.get_admin(admin_id)
        
        if not admin_info:
            await query.answer("❌ Admin não encontrado.", show_alert=True)
            return
        
        username = admin_info['username'] or f"ID {admin_id}"
        canais = db.get_all_canais(user_id=admin_id)
        
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
    """Handler para receber mídias (fotos, vídeos, documentos)"""
    if not context.user_data.get('salvando_midia', False):
        return  # Ignora mídias se não estiver no modo de salvar
    
    # Verifica se tem documento (imagem/vídeo enviado como arquivo)
    if update.message.document:
        doc = update.message.document
        # Só processa se for imagem ou vídeo
        if not doc.mime_type or (not doc.mime_type.startswith('image/') and not doc.mime_type.startswith('video/')):
            return  # Ignora documentos que não são imagens/vídeos
    
    tipo_midia = context.user_data.get('tipo_midia')
    canal_id = context.user_data.get('canal_id_midia')
    
    if not tipo_midia or not canal_id:
        return
    
    # Extrai informações da mídia
    media_info = media_handler.extract_media_info(update)
    
    if not media_info:
        await update.message.reply_text("❌ Tipo de mídia não suportado. Envie uma foto ou vídeo.")
        return
    
    if tipo_midia == 'unica':
        # Salva mídia única
        media_id = media_handler.save_media_from_message(update)
        
        if media_id:
            # Cria um grupo de mídias com apenas uma mídia
            user_id = update.message.from_user.id
            group_id = db.create_media_group(
                nome=f"Mídia Única - {datetime.now(BRASILIA_TZ).strftime('%d/%m/%Y %H:%M')}",
                user_id=user_id,
                canal_id=canal_id
            )
            
            db.add_media_to_group(group_id, media_id, ordem=1)
            
            # Limpa contexto
            for key in ['salvando_midia', 'tipo_midia', 'canal_id_midia']:
                context.user_data.pop(key, None)
            
            # Botão para voltar ao canal
            keyboard = [[InlineKeyboardButton("⬅️ Voltar ao Canal", callback_data=f"editar_canal_{canal_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "✅ <b>Mídia salva com sucesso!</b>\n\n"
                f"📦 Grupo criado: ID {group_id}\n"
                f"📸 Tipo: {media_info['media_type']}",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("❌ Erro ao salvar mídia.")
    
    elif tipo_midia == 'agrupada':
        # Adiciona mídia ao grupo temporário
        media_id = media_handler.save_media_from_message(update)
        
        if media_id:
            medias_temp = context.user_data.get('medias_temporarias', [])
            
            if len(medias_temp) >= 10:
                await update.message.reply_text("❌ Máximo de 10 mídias por grupo. Use /finalizar_grupo para salvar.")
                return
            
            medias_temp.append(media_id)
            context.user_data['medias_temporarias'] = medias_temp
            
            await update.message.reply_text(
                f"✅ <b>Mídia adicionada!</b>\n\n"
                f"📊 Total: {len(medias_temp)}/10 mídias\n\n"
                f"Envie mais mídias ou use /finalizar_grupo para salvar o grupo.",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("❌ Erro ao salvar mídia.")

@require_admin
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para mensagens de texto"""
    message_text = update.message.text
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
            success = db.add_admin(admin_id, username)
            
            if success:
                context.user_data.pop('adicionando_admin', None)
                await update.message.reply_text(
                    f"✅ <b>Admin adicionado com sucesso!</b>\n\n"
                    f"ID: <code>{admin_id}</code>\n"
                    f"Username: @{username if username else 'Sem username'}\n\n"
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

    
    # Verifica se está criando um template
    if context.user_data.get('criando_template', False):
        etapa = context.user_data.get('etapa')
        canal_id = context.user_data.get('canal_id_template')
        
        if etapa == 'template_mensagem':
            # Parseia a mensagem para extrair variáveis de link
            parsed = parser.parse_and_save_template(message_text)
            
            if not parsed:
                await update.message.reply_text(
                    "⚠️ Nenhuma variável de link encontrada.\n\n"
                    "Use o formato: <code>{link = texto}</code>\n\n"
                    "Exemplo: <code>Olá {link = clique aqui} tudo certo</code>",
                    parse_mode='HTML'
                )
                return
            
            # Salva o template temporariamente
            context.user_data['pending_template'] = parsed
            context.user_data['original_message'] = message_text
            context.user_data['links_received'] = []
            context.user_data['current_link_index'] = 0
            
            num_links = parsed['num_links']
            segmentos = parsed['segmentos']
            
            response = f"✅ <b>Template detectado!</b>\n\n"
            response += f"📝 Template: {parsed['template_mensagem']}\n\n"
            response += f"🔗 {num_links} link(s) encontrado(s):\n"
            
            for i, segmento in enumerate(segmentos, 1):
                response += f"{i}. '{segmento}'\n"
            
            # Se houver múltiplos links, mostra botões para escolher
            if num_links > 1:
                response += f"\n📌 Como configurar os links?"
                context.user_data['waiting_for_link_choice'] = True
                
                keyboard = [
                    [InlineKeyboardButton("🔗 Mesmo link para todos", callback_data="link_choice_same")],
                    [InlineKeyboardButton("🔗 Links separados", callback_data="link_choice_separate")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(response, reply_markup=reply_markup, parse_mode='HTML')
            else:
                # Se for apenas 1 link, vai direto pedir o URL
                response += f"\nEnvie o URL do link:"
                context.user_data['waiting_for_link_choice'] = False
                context.user_data['etapa'] = 'recebendo_link'
                await update.message.reply_text(response, parse_mode='HTML')
            return
        
        elif etapa == 'recebendo_link':
            # Processa o link recebido
            link_url = message_text.strip()
            
            # Valida URL
            if not (link_url.startswith('http://') or link_url.startswith('https://')):
                await update.message.reply_text(
                    "⚠️ URL inválida. Use formato: <code>http://</code> ou <code>https://</code>",
                    parse_mode='HTML'
                )
                return
            
            template_data = context.user_data['pending_template']
            num_links = template_data['num_links']
            segmentos = template_data['segmentos']
            
            # Verifica se está usando o mesmo link para todos
            if context.user_data.get('use_same_link', False):
                # Aplica o mesmo link para todos os segmentos
                links_list = [(seg, link_url) for seg in segmentos]
                
                # Salva o template
                template_id = db.save_template(
                    canal_id=canal_id,
                    template_mensagem=template_data['template_mensagem'],
                    links=links_list
                )
                
                # Cria botões
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Finalizar", callback_data="voltar_start"),
                        InlineKeyboardButton("➕ Novo Template", callback_data=f"criar_template_{canal_id}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"✅ <b>Template salvo!</b>\n\n"
                    f"📝 ID: {template_id}\n"
                    f"🔗 Links: {num_links} (mesmo URL)\n"
                    f"🌐 URL: {link_url[:50]}...",
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                
                # Limpa o contexto (mas mantém canal_id para novo template se necessário)
                for key in ['criando_template', 'etapa', 'pending_template',
                           'original_message', 'links_received', 'current_link_index',
                           'use_same_link', 'waiting_for_link_choice']:
                    context.user_data.pop(key, None)
                return
            
            # Modo separado: adiciona o link à lista
            current_index = context.user_data['current_link_index']
            
            if current_index >= len(segmentos):
                await update.message.reply_text("⚠️ Erro: índice inválido.")
                return
            
            context.user_data['links_received'].append((segmentos[current_index], link_url))
            context.user_data['current_link_index'] += 1
            
            links_received = len(context.user_data['links_received'])
            
            # Verifica se ainda faltam links
            if links_received < num_links:
                # Pede o próximo link
                next_index = context.user_data['current_link_index']
                if next_index < len(segmentos):
                    next_segmento = segmentos[next_index]
                    await update.message.reply_text(
                        f"✅ Link {links_received}/{num_links} recebido!\n\n"
                        f"Envie o URL para '{next_segmento}' ({links_received + 1}/{num_links}):",
                        parse_mode='HTML'
                    )
            else:
                # Todos os links foram recebidos, salva o template
                template_id = db.save_template(
                    canal_id=canal_id,
                    template_mensagem=template_data['template_mensagem'],
                    links=context.user_data['links_received']
                )
                
                # Cria botões
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Finalizar", callback_data="voltar_start"),
                        InlineKeyboardButton("➕ Novo Template", callback_data=f"criar_template_{canal_id}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"✅ <b>Template salvo!</b>\n\n"
                    f"📝 ID: {template_id}\n"
                    f"🔗 Links: {num_links}",
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                
                # Limpa o contexto (mas mantém canal_id para novo template se necessário)
                for key in ['criando_template', 'etapa', 'pending_template',
                           'original_message', 'links_received', 'current_link_index',
                           'use_same_link', 'waiting_for_link_choice']:
                    context.user_data.pop(key, None)
            return
    
    # Verifica se está editando um canal
    if 'editando' in context.user_data:
        dados = context.user_data['editando']
        etapa = dados.get('etapa')
        
        if etapa == 'editando_nome':
            # Atualiza o nome
            dados['nome'] = message_text
            dados['changes_made'] = True
            del dados['etapa']
            
            # Envia mensagem curta e depois mostra menu
            msg = await update.message.reply_text(f"✅ Nome atualizado para: <b>{message_text}</b>", parse_mode='HTML')
            
            # Mostra menu de edição em nova mensagem
            mensagem = f"🔧 <b>Menu de Edição</b>\n\n"
            mensagem += f"📢 <b>Nome:</b> {dados['nome']}\n"
            mensagem += f"🆔 <b>IDs:</b> {len(dados['ids'])} ID(s)\n"
            mensagem += f"🕒 <b>Horários:</b> {len(dados['horarios'])} horário(s)\n\n"
            mensagem += "Escolha o que deseja editar:"
            
            keyboard = [
                [InlineKeyboardButton("📛 Editar Nome", callback_data="edit_nome")],
                [InlineKeyboardButton("🆔 Gerenciar IDs", callback_data="edit_ids")],
                [InlineKeyboardButton("🕒 Gerenciar Horários", callback_data="edit_horarios_menu")],
            ]
            
            if dados.get('changes_made', False):
                keyboard.append([InlineKeyboardButton("✅ Salvar Alterações", callback_data="edit_salvar")])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Voltar", callback_data="editar_canal"),
                InlineKeyboardButton("✖️ Cancelar", callback_data="edit_cancelar"),
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await msg.edit_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
            return
        
        elif etapa == 'adicionando_id':
            # Adiciona novo ID
            try:
                telegram_id = int(message_text.strip())
                
                # Verifica se o bot é admin
                try:
                    bot_member = await context.bot.get_chat_member(
                        chat_id=telegram_id,
                        user_id=context.bot.id
                    )
                    
                    is_admin = (
                        bot_member.status == 'administrator' or 
                        bot_member.status == 'creator'
                    )
                    
                    if not is_admin:
                        await update.message.reply_text(
                            f"❌ Bot não é admin do canal <code>{telegram_id}</code>",
                            parse_mode='HTML'
                        )
                        return
                    
                    # Busca o nome do canal/grupo
                    try:
                        chat = await context.bot.get_chat(telegram_id)
                        chat_title = chat.title or chat.username or f"Canal {telegram_id}"
                    except Exception:
                        chat_title = f"Canal {telegram_id}"
                    
                    # Verifica se o ID já existe
                    ids = dados.get('ids', [])
                    if str(telegram_id) in ids:
                        await update.message.reply_text(
                            f"⚠️ ID <code>{telegram_id}</code> já foi adicionado.\n\n"
                            f"IDs atuais ({len(ids)}):\n" +
                            "\n".join([f"{i}. <code>{cid}</code>" for i, cid in enumerate(ids, 1)]),
                            parse_mode='HTML'
                        )
                        return
                    
                    # Adiciona o ID
                    ids.append(str(telegram_id))
                    dados['ids'] = ids
                    dados['changes_made'] = True
                    del dados['etapa']
                    
                    # Envia mensagem e mostra menu de IDs
                    msg = await update.message.reply_text(
                        f"✅ ID <code>{telegram_id}</code> adicionado!\n"
                        f"📝 <b>Nome:</b> {chat_title}",
                        parse_mode='HTML'
                    )
                    
                    # Mostra menu de IDs
                    ids_atualizados = dados.get('ids', [])
                    mensagem = "🆔 <b>Gerenciar IDs</b>\n\n"
                    
                    if ids_atualizados:
                        mensagem += "<b>IDs configurados:</b>\n"
                        for i, canal_id_str in enumerate(ids_atualizados, 1):
                            try:
                                canal_id_int = int(canal_id_str)
                                try:
                                    chat = await context.bot.get_chat(canal_id_int)
                                    chat_title = chat.title or chat.username or f"Canal {canal_id_str}"
                                    mensagem += f"{i}. <code>{canal_id_str}</code> - {chat_title}\n"
                                except Exception:
                                    mensagem += f"{i}. <code>{canal_id_str}</code>\n"
                            except ValueError:
                                mensagem += f"{i}. <code>{canal_id_str}</code>\n"
                    else:
                        mensagem += "❌ Nenhum ID configurado\n"
                    
                    mensagem += f"\nTotal: {len(ids_atualizados)} ID(s)"
                    
                    keyboard = [
                        [InlineKeyboardButton("➕ Adicionar ID", callback_data="edit_add_id")],
                    ]
                    
                    if ids_atualizados:
                        keyboard.append([InlineKeyboardButton("🗑 Remover ID", callback_data="edit_remove_id")])
                    
                    keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar")])
                    
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await msg.edit_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
                        
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'chat not found' in error_msg or 'not found' in error_msg:
                        await update.message.reply_text(
                            f"❌ Canal <code>{telegram_id}</code> não encontrado.",
                            parse_mode='HTML'
                        )
                    else:
                        await update.message.reply_text(
                            f"❌ Erro: {str(e)[:100]}",
                            parse_mode='HTML'
                        )
                        
            except ValueError:
                await update.message.reply_text(
                    "⚠️ ID inválido. Envie um número.",
                    parse_mode='HTML'
                )
            return
        
        elif etapa == 'adicionando_horario':
            # Adiciona novos horários
            horarios_texto = message_text.strip()
            horarios_novos = [h.strip() for h in horarios_texto.split(",") if h.strip()]
            
            if not horarios_novos:
                await update.message.reply_text(
                    "⚠️ Nenhum horário informado.",
                    parse_mode='HTML'
                )
                return
            
            # Valida horários
            horarios_validos = []
            horarios_invalidos = []
            
            for h in horarios_novos:
                if validar_horario(h):
                    horarios_validos.append(h)
                else:
                    horarios_invalidos.append(h)
            
            if horarios_invalidos:
                await update.message.reply_text(
                    f"❌ Horário(s) inválido(s): {', '.join(horarios_invalidos)}",
                    parse_mode='HTML'
                )
                return
            
            # Adiciona horários (evita duplicatas)
            horarios_atuais = dados.get('horarios', [])
            horarios_adicionados = []
            
            for h in horarios_validos:
                if h not in horarios_atuais:
                    horarios_atuais.append(h)
                    horarios_adicionados.append(h)
            
            dados['horarios'] = horarios_atuais
            dados['changes_made'] = True
            del dados['etapa']
            
            # Envia mensagem e mostra menu de horários
            msg = await update.message.reply_text(
                f"✅ {len(horarios_adicionados)} horário(s) adicionado(s)!",
                parse_mode='HTML'
            )
            
            # Mostra menu de horários
            horarios_atuais = dados.get('horarios', [])
            mensagem = "🕒 <b>Gerenciar Horários</b>\n\n"
            
            if horarios_atuais:
                mensagem += "<b>Horários configurados:</b>\n"
                for i, horario in enumerate(sorted(horarios_atuais), 1):
                    mensagem += f"{i}. <code>{horario}</code>\n"
            else:
                mensagem += "❌ Nenhum horário configurado\n"
            
            mensagem += f"\nTotal: {len(horarios_atuais)} horário(s)"
            
            keyboard = [
                [InlineKeyboardButton("➕ Adicionar Horário", callback_data="edit_add_horario")],
            ]
            
            if horarios_atuais:
                keyboard.append([InlineKeyboardButton("🗑 Remover Horário", callback_data="edit_remove_horario")])
            
            keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await msg.edit_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
            return
    
    # Verifica se está no fluxo de criação de canal
    if context.user_data.get('criando_canal', False):
        etapa = context.user_data.get('etapa')
        
        if etapa == 'nome':
            # Salva o nome do canal
            context.user_data['nome_canal'] = message_text
            context.user_data['etapa'] = 'id'
            context.user_data['ids_canal'] = []
            
            # Envia mensagem curta e depois edita
            msg = await update.message.reply_text("✅ Nome recebido")
            await msg.edit_text(
                f"✅ Nome: <b>{message_text}</b>\n\nEnvie o ID do canal:",
                parse_mode='HTML'
            )
        
        elif etapa == 'id':
            # Valida e verifica o ID do Telegram
            try:
                telegram_id = int(message_text.strip())
                nome_canal = context.user_data.get('nome_canal', 'N/A')
                
                # Verifica se o bot é administrador do canal
                try:
                    bot_member = await context.bot.get_chat_member(
                        chat_id=telegram_id,
                        user_id=context.bot.id
                    )
                    
                    # Verifica se o bot é administrador ou criador
                    is_admin = (
                        bot_member.status == 'administrator' or 
                        bot_member.status == 'creator'
                    )
                    
                    if not is_admin:
                        await update.message.reply_text(
                            f"❌ Bot não é admin do canal <code>{telegram_id}</code>\n\nAdicione o bot como admin e tente novamente.",
                            parse_mode='HTML'
                        )
                        return
                    
                    # Busca o nome do canal/grupo
                    try:
                        chat = await context.bot.get_chat(telegram_id)
                        chat_title = chat.title or chat.username or f"Canal {telegram_id}"
                    except Exception:
                        chat_title = f"Canal {telegram_id}"
                    
                    # Inicializa lista de IDs se não existir
                    if 'ids_canal' not in context.user_data:
                        context.user_data['ids_canal'] = []
                    
                    # Verifica se o ID já existe
                    if telegram_id in context.user_data['ids_canal']:
                        await update.message.reply_text(
                            f"⚠️ ID <code>{telegram_id}</code> já foi adicionado.\n\n"
                            f"IDs atuais ({len(context.user_data['ids_canal'])}):\n" +
                            "\n".join([f"{i}. <code>{cid}</code>" for i, cid in enumerate(context.user_data['ids_canal'], 1)]),
                            parse_mode='HTML'
                        )
                        return
                    
                    # Adiciona o ID à lista
                    context.user_data['ids_canal'].append(telegram_id)
                    
                    # Conta total de IDs
                    total_ids = len(context.user_data['ids_canal'])
                    
                    # Monta mensagem com lista de IDs
                    mensagem = f"✅ <b>Canal adicionado!</b>\n\n"
                    mensagem += f"📢 {nome_canal}\n"
                    mensagem += f"🆔 <code>{telegram_id}</code>\n"
                    mensagem += f"📝 <b>Nome:</b> {chat_title}\n"
                    mensagem += f"✅ Bot é admin\n\n"
                    mensagem += f"<b>IDs ({total_ids}):</b>\n"
                    
                    for i, canal_id in enumerate(context.user_data['ids_canal'], 1):
                        # Tenta buscar o nome do canal
                        try:
                            chat = await context.bot.get_chat(canal_id)
                            chat_title = chat.title or chat.username or f"Canal {canal_id}"
                            mensagem += f"{i}. <code>{canal_id}</code> - {chat_title}\n"
                        except Exception:
                            mensagem += f"{i}. <code>{canal_id}</code>\n"
                    
                    # Cria botões
                    keyboard = [
                        [
                            InlineKeyboardButton("➕ Adicionar outro ID", callback_data="adicionar_outro_id"),
                        ],
                        [
                            InlineKeyboardButton("✅ Confirmar", callback_data="confirmar_canal"),
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    # Envia mensagem curta primeiro
                    msg = await update.message.reply_text("✅ Canal adicionado", parse_mode='HTML')
                    
                    # Edita a mensagem anterior com detalhes e botões
                    await msg.edit_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
                    
                except Exception as e:
                    # Erro ao verificar o canal (pode ser ID inválido ou bot não está no canal)
                    error_msg = str(e).lower()
                    
                    if 'chat not found' in error_msg or 'not found' in error_msg:
                        await update.message.reply_text(
                            f"❌ Canal <code>{telegram_id}</code> não encontrado.\n\nVerifique ID, se o bot está no canal e se é admin.",
                            parse_mode='HTML'
                        )
                    else:
                        await update.message.reply_text(
                            f"❌ Erro: {str(e)[:100]}",
                            parse_mode='HTML'
                        )
                    
            except ValueError:
                await update.message.reply_text(
                    "⚠️ ID inválido. Envie um número.\nEx: <code>-1001234567890</code>",
                    parse_mode='HTML'
                )
        
        elif etapa == 'horarios':
            # Processa horários
            horarios_texto = message_text.strip()
            horarios_novos = [h.strip() for h in horarios_texto.split(",") if h.strip()]
            
            if not horarios_novos:
                await update.message.reply_text(
                    "⚠️ Nenhum horário informado. Envie horários no formato 24h, separados por vírgula.\nEx: <code>08:00, 12:30</code>",
                    parse_mode='HTML'
                )
                return
            
            # Valida horários
            horarios_validos = []
            horarios_invalidos = []
            
            for h in horarios_novos:
                if validar_horario(h):
                    horarios_validos.append(h)
                else:
                    horarios_invalidos.append(h)
            
            if horarios_invalidos:
                await update.message.reply_text(
                    f"❌ Horário(s) inválido(s): {', '.join(horarios_invalidos)}\n\nUse formato 24h (ex: 08:00, 12:30, 22:15)",
                    parse_mode='HTML'
                )
                return
            
            # Adiciona horários (evita duplicatas)
            horarios_atuais = context.user_data.get('horarios', [])
            horarios_adicionados = []
            horarios_duplicados = []
            
            for h in horarios_validos:
                if h in horarios_atuais:
                    horarios_duplicados.append(h)
                else:
                    horarios_atuais.append(h)
                    horarios_adicionados.append(h)
            
            context.user_data['horarios'] = horarios_atuais
            
            # Envia mensagem curta
            msg = await update.message.reply_text("✅ Horário(s) adicionado(s)")
            
            # Mostra menu de horários
            await mostrar_menu_horarios_text(msg, context)
            return
    
    # Verifica se está adicionando botão global
    if context.user_data.get('adicionando_global_button', False):
        etapa = context.user_data.get('global_button_etapa')
        canal_id = context.user_data.get('global_button_canal_id')
        
        if etapa == 'texto':
            # Recebeu o texto do botão
            button_text = message_text.strip()
            
            if not button_text:
                keyboard = [
                    [
                        InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_global_button"),
                        InlineKeyboardButton("⬅️ Voltar", callback_data="edit_global_buttons")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "⚠️ Texto do botão não pode estar vazio.",
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                return
            
            context.user_data['global_button_text'] = button_text
            context.user_data['global_button_etapa'] = 'url'
            
            keyboard = [
                [
                    InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_global_button"),
                    InlineKeyboardButton("⬅️ Voltar", callback_data="edit_global_buttons")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ Texto: <b>{button_text}</b>\n\n"
                f"Envie o URL do botão:\n"
                f"Ex: <code>https://example.com</code>",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            return
        
        elif etapa == 'url':
            # Recebeu o URL do botão
            button_url = message_text.strip()
            
            if not (button_url.startswith('http://') or button_url.startswith('https://')):
                keyboard = [
                    [
                        InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_global_button"),
                        InlineKeyboardButton("⬅️ Voltar", callback_data="edit_global_buttons")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "⚠️ URL inválida. Use formato: <code>http://</code> ou <code>https://</code>",
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                return
            
            button_text = context.user_data.get('global_button_text')
            
            # Busca botões existentes e adiciona novo
            existing_buttons = db.get_global_buttons(canal_id)
            buttons_list = [(btn['text'], btn['url']) for btn in existing_buttons]
            buttons_list.append((button_text, button_url))
            db.save_global_buttons(canal_id, buttons_list)
            
            # Limpa contexto
            for key in ['adicionando_global_button', 'global_button_canal_id', 
                       'global_button_etapa', 'global_button_text']:
                context.user_data.pop(key, None)
            
            # Retorna ao menu de botões globais
            dados = context.user_data.get('editando', {})
            dados['canal_id'] = canal_id
            
            global_buttons = db.get_global_buttons(canal_id)
            
            mensagem = "✅ <b>Botão global adicionado!</b>\n\n"
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
            msg = await update.message.reply_text("✅ Botão global adicionado!", parse_mode='HTML')
            await msg.edit_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
            return
    
    # Verifica se está editando botão global
    if context.user_data.get('editando_global_button', False):
        etapa = context.user_data.get('global_button_etapa')
        button_id = context.user_data.get('global_button_id')
        canal_id = context.user_data.get('global_button_canal_id')
        
        if etapa == 'texto':
            # Recebeu novo texto
            new_text = message_text.strip()
            
            if not new_text:
                keyboard = [
                    [
                        InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_global_button"),
                        InlineKeyboardButton("⬅️ Voltar", callback_data="edit_global_buttons")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "⚠️ Texto não pode estar vazio.",
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                return
            
            context.user_data['global_button_new_text'] = new_text
            context.user_data['global_button_etapa'] = 'url'
            
            keyboard = [
                [
                    InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_global_button"),
                    InlineKeyboardButton("⬅️ Voltar", callback_data="edit_global_buttons")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ Novo texto: <b>{new_text}</b>\n\n"
                f"Envie o novo URL:\n"
                f"Ex: <code>https://example.com</code>",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            return
        
        elif etapa == 'url':
            # Recebeu novo URL
            new_url = message_text.strip()
            
            if not (new_url.startswith('http://') or new_url.startswith('https://')):
                keyboard = [
                    [
                        InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_global_button"),
                        InlineKeyboardButton("⬅️ Voltar", callback_data="edit_global_buttons")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "⚠️ URL inválida. Use formato: <code>http://</code> ou <code>https://</code>",
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                return
            
            new_text = context.user_data.get('global_button_new_text')
            
            # Busca botões existentes, remove o antigo e adiciona o novo
            existing_buttons = db.get_global_buttons(canal_id)
            buttons_list = [(btn['text'], btn['url']) for btn in existing_buttons if btn['id'] != button_id]
            buttons_list.append((new_text, new_url))
            db.save_global_buttons(canal_id, buttons_list)
            
            # Limpa contexto
            for key in ['editando_global_button', 'global_button_id', 'global_button_canal_id',
                       'global_button_etapa', 'global_button_new_text']:
                context.user_data.pop(key, None)
            
            # Retorna ao menu de botões globais
            global_buttons = db.get_global_buttons(canal_id)
            
            mensagem = "✅ <b>Botão global atualizado!</b>\n\n"
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
            msg = await update.message.reply_text("✅ Botão atualizado!", parse_mode='HTML')
            await msg.edit_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
            return
    
    # Verifica se está adicionando botão inline
    if context.user_data.get('adicionando_inline_button', False):
        etapa = context.user_data.get('inline_button_etapa')
        template_id = context.user_data.get('inline_button_template_id')
        
        if etapa == 'texto':
            # Recebeu o texto do botão
            button_text = message_text.strip()
            
            if not button_text:
                await update.message.reply_text("⚠️ Texto do botão não pode estar vazio.", parse_mode='HTML')
                return
            
            context.user_data['inline_button_text'] = button_text
            context.user_data['inline_button_etapa'] = 'url'
            
            await update.message.reply_text(
                f"✅ Texto: <b>{button_text}</b>\n\n"
                f"Envie o URL do botão:\n"
                f"Ex: <code>https://example.com</code>",
                parse_mode='HTML'
            )
            return
        
        elif etapa == 'url':
            # Recebeu o URL do botão
            button_url = message_text.strip()
            
            if not (button_url.startswith('http://') or button_url.startswith('https://')):
                await update.message.reply_text(
                    "⚠️ URL inválida. Use formato: <code>http://</code> ou <code>https://</code>",
                    parse_mode='HTML'
                )
                return
            
            button_text = context.user_data.get('inline_button_text')
            
            # Busca botões existentes e adiciona novo
            existing_buttons = db.get_inline_buttons(template_id)
            buttons_list = [(btn['text'], btn['url']) for btn in existing_buttons]
            buttons_list.append((button_text, button_url))
            db.save_inline_buttons(template_id, buttons_list)
            
            # Limpa contexto
            for key in ['adicionando_inline_button', 'inline_button_template_id', 
                       'inline_button_etapa', 'inline_button_text']:
                context.user_data.pop(key, None)
            
            # Retorna ao painel de edição
            msg = await update.message.reply_text("✅ Botão inline adicionado!", parse_mode='HTML')
            await show_edit_panel(msg, template_id, context, f"✅ Botão '{button_text}' adicionado!")
            return
    
    # Verifica se está editando botão inline
    if context.user_data.get('editando_inline_button', False):
        etapa = context.user_data.get('inline_button_etapa')
        button_id = context.user_data.get('inline_button_id')
        template_id = context.user_data.get('inline_button_template_id')
        
        if etapa == 'texto':
            # Recebeu novo texto
            new_text = message_text.strip()
            
            if not new_text:
                await update.message.reply_text("⚠️ Texto não pode estar vazio.", parse_mode='HTML')
                return
            
            context.user_data['inline_button_new_text'] = new_text
            context.user_data['inline_button_etapa'] = 'url'
            
            await update.message.reply_text(
                f"✅ Novo texto: <b>{new_text}</b>\n\n"
                f"Envie o novo URL:\n"
                f"Ex: <code>https://example.com</code>",
                parse_mode='HTML'
            )
            return
        
        elif etapa == 'url':
            # Recebeu novo URL
            new_url = message_text.strip()
            
            if not (new_url.startswith('http://') or new_url.startswith('https://')):
                await update.message.reply_text(
                    "⚠️ URL inválida. Use formato: <code>http://</code> ou <code>https://</code>",
                    parse_mode='HTML'
                )
                return
            
            new_text = context.user_data.get('inline_button_new_text')
            
            # Busca botões existentes, remove o antigo e adiciona o novo
            existing_buttons = db.get_inline_buttons(template_id)
            buttons_list = [(btn['text'], btn['url']) for btn in existing_buttons if btn['id'] != button_id]
            buttons_list.append((new_text, new_url))
            db.save_inline_buttons(template_id, buttons_list)
            
            # Limpa contexto
            for key in ['editando_inline_button', 'inline_button_id', 'inline_button_template_id',
                       'inline_button_etapa', 'inline_button_new_text']:
                context.user_data.pop(key, None)
            
            # Retorna ao painel
            msg = await update.message.reply_text("✅ Botão atualizado!", parse_mode='HTML')
            await show_edit_panel(msg, template_id, context, f"✅ Botão atualizado para '{new_text}'!")
            return
    
    # Verifica se está editando links de template
    if 'editing_all_links' in context.user_data:
        # Editando todos os links
        link_url = message_text.strip()
        
        if not (link_url.startswith('http://') or link_url.startswith('https://')):
            await update.message.reply_text(
                "⚠️ URL inválida. Use formato: <code>http://</code> ou <code>https://</code>",
                parse_mode='HTML'
            )
            return
        
        template_id = context.user_data['editing_template_id']
        num_links = context.user_data['editing_num_links']
        
        # Atualiza todos os links
        updated_count = db.update_all_links(template_id, link_url)
        
        if updated_count > 0:
            # Limpa contexto
            del context.user_data['editing_all_links']
            del context.user_data['editing_template_id']
            del context.user_data['editing_num_links']
            
            # Retorna ao painel de edição
            url_display = link_url if len(link_url) <= 50 else link_url[:47] + "..."
            success_msg = f"Todos os {updated_count} segmentos atualizados para: {url_display}"
            
            # Envia mensagem de sucesso e mostra painel
            msg = await update.message.reply_text("✅ Links atualizados!", parse_mode='HTML')
            await show_edit_panel(msg, template_id, context, success_msg)
        else:
            await update.message.reply_text("❌ Erro ao atualizar links.", parse_mode='HTML')
        return
    
    if 'editing_link_id' in context.user_data:
        # Editando um link específico
        link_url = message_text.strip()
        
        if not (link_url.startswith('http://') or link_url.startswith('https://')):
            await update.message.reply_text(
                "⚠️ URL inválida. Use formato: <code>http://</code> ou <code>https://</code>",
                parse_mode='HTML'
            )
            return
        
        link_id = context.user_data['editing_link_id']
        template_id = context.user_data['editing_template_id']
        segmento = context.user_data['editing_segmento']
        ordem = context.user_data['editing_ordem']
        
        # Atualiza o link
        updated = db.update_link(link_id, link_url)
        
        if updated:
            # Limpa contexto
            del context.user_data['editing_link_id']
            del context.user_data['editing_template_id']
            del context.user_data['editing_segmento']
            del context.user_data['editing_ordem']
            
            # Retorna ao painel de edição
            url_display = link_url if len(link_url) <= 50 else link_url[:47] + "..."
            success_msg = f"Segmento {ordem} ('{segmento}') atualizado: {url_display}"
            await show_edit_panel(update.message, template_id, context, success_msg)
        else:
            await update.message.reply_text("❌ Erro ao atualizar link.", parse_mode='HTML')
        return
    
    # Verifica se está mudando link global (todos os links)
    if 'mudando_link_global' in context.user_data:
        link_url = message_text.strip()
        
        if not (link_url.startswith('http://') or link_url.startswith('https://')):
            await update.message.reply_text(
                "⚠️ URL inválida. Use formato: <code>http://</code> ou <code>https://</code>",
                parse_mode='HTML'
            )
            return
        
        template_id = context.user_data['mudando_link_template_id']
        
        # Atualiza todos os links sem exceção
        updated_count = db.update_all_links(template_id, link_url)
        
        if updated_count > 0:
            # Limpa contexto
            del context.user_data['mudando_link_global']
            del context.user_data['mudando_link_template_id']
            
            # Retorna ao painel
            url_display = link_url if len(link_url) <= 50 else link_url[:47] + "..."
            success_msg = f"✅ {updated_count} link(s) atualizado(s) globalmente para: {url_display}"
            
            msg = await update.message.reply_text("✅ Links atualizados!", parse_mode='HTML')
            await show_edit_panel(msg, template_id, context, success_msg)
        else:
            await update.message.reply_text("❌ Erro ao atualizar links.", parse_mode='HTML')
        return
    
    # Verifica se está mudando link de bot (Telegram)
    if 'mudando_link_bot' in context.user_data:
        link_url = message_text.strip()
        
        if not (link_url.startswith('http://') or link_url.startswith('https://')):
            await update.message.reply_text(
                "⚠️ URL inválida. Use formato: <code>http://</code> ou <code>https://</code>",
                parse_mode='HTML'
            )
            return
        
        # Verifica se o novo link é um bot do Telegram
        if not link_url.startswith('https://t.me/'):
            await update.message.reply_text(
                "⚠️ O link deve ser de um bot do Telegram (começar com https://t.me/)",
                parse_mode='HTML'
            )
            return
        
        # Extrai username do novo bot
        new_bot_username = link_url.replace('https://t.me/', '').split('?')[0]
        
        if not new_bot_username.lower().endswith('bot'):
            await update.message.reply_text(
                "⚠️ O username deve terminar com 'bot' (ex: https://t.me/meubot)",
                parse_mode='HTML'
            )
            return
        
        template_id = context.user_data['mudando_link_template_id']
        template = db.get_template_with_link_ids(template_id)
        
        if not template:
            await update.message.reply_text("❌ Template não encontrado.", parse_mode='HTML')
            return
        
        updated_count = 0
        links = template['links']
        
        for link_id, segmento, url_atual, ordem in links:
            # Verifica se é um link de bot do Telegram
            if url_atual.startswith('https://t.me/'):
                # Extrai o username do bot atual
                bot_part = url_atual.replace('https://t.me/', '')
                username_atual = bot_part.split('?')[0]
                
                # Só altera se terminar com 'bot'
                if username_atual.lower().endswith('bot'):
                    # Verifica se tem parâmetros
                    if '?' in url_atual:
                        # Preserva os parâmetros
                        params = url_atual.split('?', 1)[1]
                        new_url = f"https://t.me/{new_bot_username}?{params}"
                    else:
                        # Sem parâmetros, substitui completo
                        new_url = f"https://t.me/{new_bot_username}"
                    
                    # Atualiza o link
                    if db.update_link(link_id, new_url):
                        updated_count += 1
        
        # Limpa contexto
        del context.user_data['mudando_link_bot']
        del context.user_data['mudando_link_template_id']
        
        if updated_count > 0:
            success_msg = f"✅ {updated_count} link(s) de bot atualizado(s) para: {new_bot_username}"
            msg = await update.message.reply_text("✅ Links de bot atualizados!", parse_mode='HTML')
            await show_edit_panel(msg, template_id, context, success_msg)
        else:
            msg = await update.message.reply_text("⚠️ Nenhum link de bot encontrado para atualizar.", parse_mode='HTML')
            await show_edit_panel(msg, template_id, context)
        return
    
    # Verifica se está mudando link externo (não Telegram)
    if 'mudando_link_externo' in context.user_data:
        link_url = message_text.strip()
        
        if not (link_url.startswith('http://') or link_url.startswith('https://')):
            await update.message.reply_text(
                "⚠️ URL inválida. Use formato: <code>http://</code> ou <code>https://</code>",
                parse_mode='HTML'
            )
            return
        
        template_id = context.user_data['mudando_link_template_id']
        template = db.get_template_with_link_ids(template_id)
        
        if not template:
            await update.message.reply_text("❌ Template não encontrado.", parse_mode='HTML')
            return
        
        updated_count = 0
        links = template['links']
        
        for link_id, segmento, url_atual, ordem in links:
            # Só atualiza se NÃO for link do Telegram
            if not url_atual.startswith('https://t.me/'):
                if db.update_link(link_id, link_url):
                    updated_count += 1
        
        # Limpa contexto
        del context.user_data['mudando_link_externo']
        del context.user_data['mudando_link_template_id']
        
        if updated_count > 0:
            url_display = link_url if len(link_url) <= 50 else link_url[:47] + "..."
            success_msg = f"✅ {updated_count} link(s) externo(s) atualizado(s) para: {url_display}"
            msg = await update.message.reply_text("✅ Links externos atualizados!", parse_mode='HTML')
            await show_edit_panel(msg, template_id, context, success_msg)
        else:
            msg = await update.message.reply_text("⚠️ Nenhum link externo encontrado para atualizar.", parse_mode='HTML')
            await show_edit_panel(msg, template_id, context)
        return
    
    # Verifica se está mudando link global de TODOS os templates do canal
    if 'mudando_link_global_canal' in context.user_data:
        link_url = message_text.strip()
        
        if not (link_url.startswith('http://') or link_url.startswith('https://')):
            await update.message.reply_text(
                "⚠️ URL inválida. Use formato: <code>http://</code> ou <code>https://</code>",
                parse_mode='HTML'
            )
            return
        
        canal_id = context.user_data['mudando_link_canal_id']
        templates = db.get_templates_by_canal(canal_id)
        
        total_updated = 0
        templates_affected = 0
        
        for template in templates:
            template_id = template['id']
            updated_count = db.update_all_links(template_id, link_url)
            if updated_count > 0:
                total_updated += updated_count
                templates_affected += 1
        
        # Limpa contexto
        del context.user_data['mudando_link_global_canal']
        del context.user_data['mudando_link_canal_id']
        
        if total_updated > 0:
            url_display = link_url if len(link_url) <= 50 else link_url[:47] + "..."
            keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="edit_templates")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ <b>Links atualizados globalmente!</b>\n\n"
                f"📄 Templates afetados: {templates_affected}\n"
                f"🔗 Total de links atualizados: {total_updated}\n"
                f"🌐 Novo link: {url_display}",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="edit_templates")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "❌ Nenhum link foi atualizado.",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        return
    
    # Verifica se está mudando link de bot de TODOS os templates do canal
    if 'mudando_link_bot_canal' in context.user_data:
        link_url = message_text.strip()
        
        if not (link_url.startswith('http://') or link_url.startswith('https://')):
            await update.message.reply_text(
                "⚠️ URL inválida. Use formato: <code>http://</code> ou <code>https://</code>",
                parse_mode='HTML'
            )
            return
        
        # Verifica se o novo link é um bot do Telegram
        if not link_url.startswith('https://t.me/'):
            await update.message.reply_text(
                "⚠️ O link deve ser de um bot do Telegram (começar com https://t.me/)",
                parse_mode='HTML'
            )
            return
        
        # Extrai username do novo bot
        new_bot_username = link_url.replace('https://t.me/', '').split('?')[0]
        
        if not new_bot_username.lower().endswith('bot'):
            await update.message.reply_text(
                "⚠️ O username deve terminar com 'bot' (ex: https://t.me/meubot)",
                parse_mode='HTML'
            )
            return
        
        canal_id = context.user_data['mudando_link_canal_id']
        templates = db.get_templates_by_canal(canal_id)
        
        total_updated = 0
        templates_affected = 0
        
        for template in templates:
            template_id = template['id']
            template_data = db.get_template_with_link_ids(template_id)
            
            if not template_data:
                continue
            
            links = template_data['links']
            template_had_updates = False
            
            for link_id, segmento, url_atual, ordem in links:
                # Verifica se é um link de bot do Telegram
                if url_atual.startswith('https://t.me/'):
                    # Extrai o username do bot atual
                    bot_part = url_atual.replace('https://t.me/', '')
                    username_atual = bot_part.split('?')[0]
                    
                    # Só altera se terminar com 'bot'
                    if username_atual.lower().endswith('bot'):
                        # Verifica se tem parâmetros
                        if '?' in url_atual:
                            # Preserva os parâmetros
                            params = url_atual.split('?', 1)[1]
                            new_url = f"https://t.me/{new_bot_username}?{params}"
                        else:
                            # Sem parâmetros, substitui completo
                            new_url = f"https://t.me/{new_bot_username}"
                        
                        # Atualiza o link
                        if db.update_link(link_id, new_url):
                            total_updated += 1
                            template_had_updates = True
            
            if template_had_updates:
                templates_affected += 1
        
        # Limpa contexto
        del context.user_data['mudando_link_bot_canal']
        del context.user_data['mudando_link_canal_id']
        
        if total_updated > 0:
            keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="edit_templates")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ <b>Links de bot atualizados!</b>\n\n"
                f"📄 Templates afetados: {templates_affected}\n"
                f"🔗 Total de links atualizados: {total_updated}\n"
                f"🤖 Novo bot: {new_bot_username}",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="edit_templates")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "⚠️ Nenhum link de bot encontrado para atualizar.",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        return
    
    # Verifica se está mudando link externo de TODOS os templates do canal
    if 'mudando_link_externo_canal' in context.user_data:
        link_url = message_text.strip()
        
        if not (link_url.startswith('http://') or link_url.startswith('https://')):
            await update.message.reply_text(
                "⚠️ URL inválida. Use formato: <code>http://</code> ou <code>https://</code>",
                parse_mode='HTML'
            )
            return
        
        canal_id = context.user_data['mudando_link_canal_id']
        templates = db.get_templates_by_canal(canal_id)
        
        total_updated = 0
        templates_affected = 0
        
        for template in templates:
            template_id = template['id']
            template_data = db.get_template_with_link_ids(template_id)
            
            if not template_data:
                continue
            
            links = template_data['links']
            template_had_updates = False
            
            for link_id, segmento, url_atual, ordem in links:
                # Só atualiza se NÃO for link do Telegram
                if not url_atual.startswith('https://t.me/'):
                    if db.update_link(link_id, link_url):
                        total_updated += 1
                        template_had_updates = True
            
            if template_had_updates:
                templates_affected += 1
        
        # Limpa contexto
        del context.user_data['mudando_link_externo_canal']
        del context.user_data['mudando_link_canal_id']
        
        if total_updated > 0:
            url_display = link_url if len(link_url) <= 50 else link_url[:47] + "..."
            keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="edit_templates")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ <b>Links externos atualizados!</b>\n\n"
                f"📄 Templates afetados: {templates_affected}\n"
                f"🔗 Total de links atualizados: {total_updated}\n"
                f"🌐 Novo link: {url_display}",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="edit_templates")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "⚠️ Nenhum link externo encontrado para atualizar.",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        return


def validar_horario(h):
    """Valida formato de horário (HH:MM em 24h)"""
    return re.match(r"^(2[0-3]|[01]?\d):[0-5]\d$", h)

async def mostrar_menu_horarios(query_or_message, context):
    """Mostra o menu de gerenciamento de horários"""
    horarios = context.user_data.get('horarios', [])
    
    mensagem = "🕒 <b>Gerenciar Horários</b>\n\n"
    
    if horarios:
        mensagem += "<b>Horários configurados:</b>\n"
        for i, horario in enumerate(sorted(horarios), 1):
            mensagem += f"{i}. <code>{horario}</code>\n"
    else:
        mensagem += "❌ Nenhum horário configurado\n"
    
    mensagem += f"\nTotal: {len(horarios)} horário(s)"
    
    keyboard = [
        [
            InlineKeyboardButton("➕ Adicionar Horário", callback_data="adicionar_horario"),
        ],
    ]
    
    if horarios:
        keyboard.append([
            InlineKeyboardButton("🗑 Remover Horário", callback_data="remover_horario"),
        ])
    
    keyboard.append([
        InlineKeyboardButton("✅ Confirmar", callback_data="confirmar_horarios"),
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if hasattr(query_or_message, 'edit_message_text'):
        await query_or_message.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await query_or_message.edit_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')

async def mostrar_menu_horarios_text(message, context):
    """Versão para editar mensagem de texto"""
    horarios = context.user_data.get('horarios', [])
    
    mensagem = "🕒 <b>Gerenciar Horários</b>\n\n"
    
    if horarios:
        mensagem += "<b>Horários configurados:</b>\n"
        for i, horario in enumerate(sorted(horarios), 1):
            mensagem += f"{i}. <code>{horario}</code>\n"
    else:
        mensagem += "❌ Nenhum horário configurado\n"
    
    mensagem += f"\nTotal: {len(horarios)} horário(s)"
    
    keyboard = [
        [
            InlineKeyboardButton("➕ Adicionar Horário", callback_data="adicionar_horario"),
        ],
    ]
    
    if horarios:
        keyboard.append([
            InlineKeyboardButton("🗑 Remover Horário", callback_data="remover_horario"),
        ])
    
    keyboard.append([
        InlineKeyboardButton("✅ Confirmar", callback_data="confirmar_horarios"),
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.edit_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')

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

async def mostrar_menu_ids(query, context):
    """Mostra o menu de gerenciamento de IDs"""
    dados = context.user_data.get('editando', {})
    ids = dados.get('ids', [])
    
    mensagem = "🆔 <b>Gerenciar IDs</b>\n\n"
    
    if ids:
        mensagem += "<b>IDs configurados:</b>\n"
        for i, canal_id_str in enumerate(ids, 1):
            try:
                canal_id_int = int(canal_id_str)
                try:
                    chat = await context.bot.get_chat(canal_id_int)
                    chat_title = chat.title or chat.username or f"Canal {canal_id_str}"
                    mensagem += f"{i}. <code>{canal_id_str}</code> - {chat_title}\n"
                except Exception:
                    mensagem += f"{i}. <code>{canal_id_str}</code>\n"
            except ValueError:
                mensagem += f"{i}. <code>{canal_id_str}</code>\n"
    else:
        mensagem += "❌ Nenhum ID configurado\n"
    
    mensagem += f"\nTotal: {len(ids)} ID(s)"
    
    keyboard = [
        [
            InlineKeyboardButton("➕ Adicionar ID", callback_data="edit_add_id"),
        ],
    ]
    
    if ids:
        keyboard.append([
            InlineKeyboardButton("🗑 Remover ID", callback_data="edit_remove_id"),
        ])
    
    keyboard.append([
        InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar"),
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')

async def mostrar_menu_horarios_edicao(query, context):
    """Mostra o menu de gerenciamento de horários na edição"""
    dados = context.user_data.get('editando', {})
    horarios = dados.get('horarios', [])
    
    mensagem = "🕒 <b>Gerenciar Horários</b>\n\n"
    
    if horarios:
        mensagem += "<b>Horários configurados:</b>\n"
        for i, horario in enumerate(sorted(horarios), 1):
            mensagem += f"{i}. <code>{horario}</code>\n"
    else:
        mensagem += "❌ Nenhum horário configurado\n"
    
    mensagem += f"\nTotal: {len(horarios)} horário(s)"
    
    keyboard = [
        [
            InlineKeyboardButton("➕ Adicionar Horário", callback_data="edit_add_horario"),
        ],
    ]
    
    if horarios:
        keyboard.append([
            InlineKeyboardButton("🗑 Remover Horário", callback_data="edit_remove_horario"),
        ])
    
    keyboard.append([
        InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar"),
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')

async def show_edit_panel(query_or_message, template_id: int, context, success_message: str = None):
    """
    Mostra o painel de edição de links de um template
    Pode receber CallbackQuery ou Message
    """
    template = db.get_template_with_link_ids(template_id)
    
    if not template:
        if hasattr(query_or_message, 'edit_message_text'):
            await query_or_message.edit_message_text("❌ Template não encontrado.", parse_mode='HTML')
        else:
            await query_or_message.reply_text("❌ Template não encontrado.", parse_mode='HTML')
        return
    
    template_mensagem = template['template_mensagem']
    links = template['links']  # [(link_id, segmento, url, ordem), ...]
    inline_buttons = template.get('inline_buttons', [])  # Lista de dicionários
    
    # Monta mensagem
    message_text = f"📝 <b>Template ID: {template_id}</b>\n\n"
    message_text += f"📄 <b>Mensagem:</b>\n{template_mensagem}\n\n"
    
    if success_message:
        message_text += f"✅ {success_message}\n\n"
    
    message_text += f"🔗 <b>Segmentos ({len(links)}):</b>\n\n"
    
    # Cria botões para cada segmento
    keyboard = []
    for link_id, segmento, url, ordem in links:
        url_display = url if len(url) <= 40 else url[:37] + "..."
        message_text += f"{ordem}. '{segmento}'\n   → {url_display}\n\n"
        
        segmento_display = segmento[:20] + "..." if len(segmento) > 20 else segmento
        keyboard.append([
            InlineKeyboardButton(
                f"✏️ Segmento {ordem}: {segmento_display}",
                callback_data=f"edit_link_{link_id}"
            )
        ])
    
    # Botão para editar todos
    if len(links) > 1:
        keyboard.append([
            InlineKeyboardButton("🔗 Editar todos para o mesmo link", callback_data=f"edit_all_{template_id}")
        ])
    
    # Seção de botões inline
    message_text += f"\n🔘 <b>Botões Inline ({len(inline_buttons)}):</b>\n\n"
    if inline_buttons:
        for button in inline_buttons:
            button_text = button['text']
            button_url = button['url']
            button_id = button['id']
            ordem = button['ordem']
            url_display = button_url if len(button_url) <= 40 else button_url[:37] + "..."
            message_text += f"{ordem}. '{button_text}'\n   → {url_display}\n\n"
            
            button_display = button_text[:20] + "..." if len(button_text) > 20 else button_text
            keyboard.append([
                InlineKeyboardButton(
                    f"✏️ Botão {ordem}: {button_display}",
                    callback_data=f"edit_inline_button_{button_id}"
                )
            ])
            keyboard.append([
                InlineKeyboardButton(
                    f"🗑️ Deletar Botão {ordem}",
                    callback_data=f"deletar_inline_button_{button_id}"
                )
            ])
    else:
        message_text += "❌ Nenhum botão inline\n\n"
    
    # Botão para adicionar botão inline
    keyboard.append([
        InlineKeyboardButton("➕ Adicionar Botão Inline", callback_data=f"adicionar_inline_button_{template_id}")
    ])
    
    # Botões de navegação
    dados = context.user_data.get('editando', {})
    canal_id = dados.get('canal_id')
    if canal_id:
        keyboard.append([
            InlineKeyboardButton("⬅️ Voltar", callback_data="edit_templates"),
            InlineKeyboardButton("❌ Cancelar", callback_data="edit_cancel")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton("❌ Cancelar", callback_data="edit_cancel")
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Envia ou edita mensagem
    if hasattr(query_or_message, 'edit_message_text'):
        await query_or_message.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        # Se for Message, edita a mensagem anterior
        await query_or_message.edit_text(message_text, reply_markup=reply_markup, parse_mode='HTML')

async def mostrar_menu_medias(query, context):
    """Mostra o menu de gerenciamento de mídias"""
    dados = context.user_data.get('editando', {})
    canal_id = dados.get('canal_id')
    user_id = query.from_user.id
    
    if not canal_id:
        await query.edit_message_text("❌ Erro: canal não encontrado.", parse_mode='HTML')
        return
    
    # Busca grupos de mídias do canal
    media_groups = db.get_media_groups_by_user(user_id, canal_id)
    
    mensagem = "📸 <b>Gerenciar Mídias</b>\n\n"
    mensagem += "Escolha uma opção:\n\n"
    
    if media_groups:
        mensagem += f"📦 <b>Grupos de Mídias ({len(media_groups)}):</b>\n"
        for group in media_groups[:5]:  # Mostra até 5
            mensagem += f"   • {group['nome']} ({group['media_count']} mídias)\n"
        if len(media_groups) > 5:
            mensagem += f"   ... e mais {len(media_groups) - 5}\n"
    else:
        mensagem += "❌ Nenhum grupo de mídias criado ainda.\n"
    
    keyboard = [
        [
            InlineKeyboardButton("📸 Salvar Mídia Única", callback_data="salvar_midia_unica"),
        ],
        [
            InlineKeyboardButton("📦 Salvar Mídia Agrupada", callback_data="salvar_midia_agrupada"),
        ],
    ]
    
    if media_groups:
        keyboard.append([
            InlineKeyboardButton("📋 Ver Grupos de Mídias", callback_data="listar_grupos_midias")
        ])
        keyboard.append([
            InlineKeyboardButton("⚡ Associar Template Automaticamente", callback_data="associar_template_automatico")
        ])
    
    keyboard.append([
        InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')

async def mostrar_detalhes_grupo_midia(query, context, group_id: int):
    """Mostra detalhes de um grupo de mídias"""
    group = db.get_media_group(group_id)
    
    if not group:
        await query.edit_message_text("❌ Grupo de mídias não encontrado.", parse_mode='HTML')
        return
    
    mensagem = f"📦 <b>{group['nome']}</b>\n\n"
    mensagem += f"🆔 ID: {group_id}\n"
    mensagem += f"📊 Mídias: {len(group['medias'])}\n\n"
    
    if group['medias']:
        mensagem += "<b>Mídias no grupo:</b>\n"
        for i, media in enumerate(group['medias'], 1):
            tipo_emoji = "📸" if media['media_type'] == 'photo' else "🎥"
            mensagem += f"{i}. {tipo_emoji} {media['media_type']}\n"
    
    # Verifica se tem template associado
    template_info = ""
    if group.get('template_id'):
        template = db.get_template(group['template_id'])
        if template:
            template_info = f"\n📝 Template: ID {group['template_id']}"
    else:
        # Verifica se há templates disponíveis no canal para uso automático
        if group.get('canal_id'):
            templates = db.get_templates_by_canal(group['canal_id'])
            if templates:
                template_info = f"\n📝 Template: ⚡ Automático (usará qualquer template do canal)"
            else:
                template_info = "\n📝 Template: ❌ Nenhum template disponível"
        else:
            template_info = "\n📝 Template: ❌ Nenhum template associado"
    
    mensagem += template_info
    
    # Busca botões globais
    global_buttons_info = ""
    if group.get('canal_id'):
        global_buttons = db.get_global_buttons(group['canal_id'])
        if global_buttons:
            global_buttons_info = f"\n🔘 Botões Globais: {len(global_buttons)} botão(ões)"
        else:
            global_buttons_info = "\n🔘 Botões Globais: ❌ Nenhum"
    
    mensagem += global_buttons_info
    
    keyboard = [
        [
            InlineKeyboardButton("👁️ Preview", callback_data=f"preview_grupo_midia_{group_id}"),
        ],
    ]
    
    # Botões de template
    if group.get('template_id'):
        keyboard.append([
            InlineKeyboardButton("📝 Trocar Template", callback_data=f"associar_template_grupo_{group_id}"),
            InlineKeyboardButton("❌ Remover Template", callback_data=f"remover_template_grupo_{group_id}"),
        ])
    else:
        keyboard.append([
            InlineKeyboardButton("📝 Associar Template", callback_data=f"associar_template_grupo_{group_id}"),
        ])
    
    keyboard.append([
        InlineKeyboardButton("🗑️ Deletar", callback_data=f"deletar_grupo_midia_{group_id}"),
    ])
    keyboard.append([
        InlineKeyboardButton("⬅️ Voltar", callback_data="edit_medias")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')

async def enviar_preview_grupo_midia(query, context, group_id: int):
    """Envia preview do grupo de mídias com template e botões"""
    # Busca o grupo de mídias
    group = db.get_media_group(group_id)
    
    if not group:
        await query.edit_message_text("❌ Grupo de mídias não encontrado.", parse_mode='HTML')
        return
    
    if not group.get('medias'):
        await query.edit_message_text("❌ Grupo de mídias está vazio.", parse_mode='HTML')
        return
    
    # Busca template se houver associado
    # Se não houver, o media_handler buscará automaticamente
    template = None
    if group.get('template_id'):
        template = db.get_template(group['template_id'])
    
    # Busca botões globais do canal (sempre busca, mesmo sem template)
    global_buttons = None
    if group.get('canal_id'):
        global_buttons = db.get_global_buttons(group['canal_id'])
        # Se não encontrou botões, deixa como None (o media_handler tentará buscar novamente)
    
    # Envia mensagem de carregamento
    await query.answer("📤 Enviando preview...")
    await query.edit_message_text("📤 <b>Enviando preview...</b>", parse_mode='HTML')
    
    # Envia o preview
    try:
        user_id = query.from_user.id
        success = await media_handler.send_media_group_with_template(
            context=context,
            chat_id=user_id,  # Envia para o próprio usuário como preview
            media_group=group,
            template=template,
            global_buttons=global_buttons,
            database=db,
            use_auto_template=True
        )
        
        if success:
            # Volta para os detalhes do grupo
            keyboard = [
                [
                    InlineKeyboardButton("⬅️ Voltar", callback_data=f"ver_grupo_midia_{group_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "✅ <b>Preview enviado!</b>\n\n"
                "Verifique a mensagem acima para ver como ficará o grupo de mídias com template e botões aplicados.",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await query.edit_message_text(
                "❌ Erro ao enviar preview. Verifique se o grupo tem mídias válidas.",
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Erro ao enviar preview: {e}")
        await query.edit_message_text(
            f"❌ Erro ao enviar preview: {str(e)[:100]}",
            parse_mode='HTML'
        )

@require_admin
async def finalizar_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando para finalizar criação de grupo de mídias"""
    if not context.user_data.get('salvando_midia') or context.user_data.get('tipo_midia') != 'agrupada':
        await update.message.reply_text("❌ Você não está criando um grupo de mídias.")
        return
    
    medias_temp = context.user_data.get('medias_temporarias', [])
    
    if len(medias_temp) == 0:
        await update.message.reply_text("❌ Nenhuma mídia foi adicionada ao grupo.")
        return
    
    if len(medias_temp) > 10:
        await update.message.reply_text("❌ Máximo de 10 mídias por grupo. Remova algumas mídias.")
        return
    
    # Cria o grupo de mídias com nome temporário
    user_id = update.message.from_user.id
    canal_id = context.user_data.get('canal_id_midia')
    
    # Cria com nome temporário
    group_id = db.create_media_group(
        nome="Grupo Temp",
        user_id=user_id,
        canal_id=canal_id
    )
    
    # Atualiza o nome com o ID
    novo_nome = f"Grupo {group_id}"
    db.update_media_group(group_id, nome=novo_nome)
    
    # Adiciona todas as mídias ao grupo
    for ordem, media_id in enumerate(medias_temp, start=1):
        db.add_media_to_group(group_id, media_id, ordem=ordem)
    
    # Limpa contexto
    for key in ['salvando_midia', 'tipo_midia', 'canal_id_midia', 
               'medias_temporarias', 'criando_grupo', 'etapa_grupo']:
        context.user_data.pop(key, None)
    
    # Botão para voltar ao canal
    keyboard = [[InlineKeyboardButton("⬅️ Voltar ao Canal", callback_data=f"editar_canal_{canal_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ <b>Grupo de mídias criado com sucesso!</b>\n\n"
        f"📦 Nome: {novo_nome}\n"
        f"🆔 ID: {group_id}\n"
        f"📊 Mídias: {len(medias_temp)}",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

# Variável global para o scheduler
scheduler = None

async def post_init(application: Application) -> None:
    """Inicializa o scheduler após o bot estar pronto"""
    global scheduler
    
    # Define os comandos do bot
    await set_bot_commands(application)
    
    # Aguarda um pouco para garantir que o bot está totalmente inicializado
    import asyncio
    await asyncio.sleep(2)
    
    scheduler = MediaScheduler(db, media_handler, application.bot)
    
    # Inicia o scheduler em background
    asyncio.create_task(scheduler.run_scheduler())
    logger.info("🚀 Scheduler de mídias iniciado!")

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
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
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

