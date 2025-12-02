import os
import re
import logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from database import Database
from parser import MessageParser

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

# Inicializa banco de dados e parser
db = Database()
parser = MessageParser()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para o comando /start"""
    welcome_message = "🤖 <b>Bot de Vagas</b>\n\nEscolha uma opção:"
    
    # Cria botões inline
    keyboard = [
        [
            InlineKeyboardButton("📢 Criar Canal", callback_data="criar_canal"),
        ],
        [
            InlineKeyboardButton("✏️ Editar Canal", callback_data="editar_canal"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

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
        welcome_message = "🤖 <b>Bot de Vagas</b>\n\nEscolha uma opção:"
        
        keyboard = [
            [
                InlineKeyboardButton("📢 Criar Canal", callback_data="criar_canal"),
            ],
            [
                InlineKeyboardButton("✏️ Editar Canal", callback_data="editar_canal"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            welcome_message,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    
    elif query.data.startswith("criar_template_"):
        # Inicia criação de template para um canal
        canal_id = int(query.data.split("_")[-1])
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
        
        if not canal or canal['user_id'] != user_id:
            await query.edit_message_text(
                "❌ Canal não encontrado ou você não tem permissão para editá-lo.",
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
        
        # Converte para formato de tuplas (segmento, link_url)
        links_tuples = [(link['segmento'], link['link']) for link in links]
        
        # Formata a mensagem com links HTML
        formatted_message = parser.format_message_with_links(template_mensagem, links_tuples)
        
        # Monta mensagem com informações
        preview_text = f"👁️ <b>Preview - Template ID: {template_id}</b>\n\n"
        preview_text += f"📄 <b>Mensagem formatada:</b>\n\n"
        preview_text += formatted_message
        
        # Botões para voltar
        keyboard = [
            [
                InlineKeyboardButton("⬅️ Voltar", callback_data="edit_templates"),
                InlineKeyboardButton("✏️ Editar Links", callback_data=f"edit_template_{template_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
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
    
    elif query.data == "edit_cancel":
        # Cancela edição de links
        await query.edit_message_text("❌ Edição cancelada.", parse_mode='HTML')
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
            mensagem += "📝 <b>Criar template de mensagem?</b>"
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Sim", callback_data=f"criar_template_{canal_id}"),
                    InlineKeyboardButton("❌ Não", callback_data="voltar_start"),
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
    

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para mensagens de texto"""
    message_text = update.message.text
    
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
                    
                    # Adiciona o ID
                    ids = dados.get('ids', [])
                    if str(telegram_id) not in ids:
                        ids.append(str(telegram_id))
                        dados['ids'] = ids
                        dados['changes_made'] = True
                        del dados['etapa']
                        
                        # Envia mensagem e mostra menu de IDs
                        msg = await update.message.reply_text(
                            f"✅ ID <code>{telegram_id}</code> adicionado!",
                            parse_mode='HTML'
                        )
                        
                        # Mostra menu de IDs
                        ids = dados.get('ids', [])
                        mensagem = "🆔 <b>Gerenciar IDs</b>\n\n"
                        
                        if ids:
                            mensagem += "<b>IDs configurados:</b>\n"
                            for i, canal_id in enumerate(ids, 1):
                                mensagem += f"{i}. <code>{canal_id}</code>\n"
                        else:
                            mensagem += "❌ Nenhum ID configurado\n"
                        
                        mensagem += f"\nTotal: {len(ids)} ID(s)"
                        
                        keyboard = [
                            [InlineKeyboardButton("➕ Adicionar ID", callback_data="edit_add_id")],
                        ]
                        
                        if ids:
                            keyboard.append([InlineKeyboardButton("🗑 Remover ID", callback_data="edit_remove_id")])
                        
                        keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar")])
                        
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await msg.edit_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
                    else:
                        await update.message.reply_text(
                            "⚠️ Este ID já está na lista.",
                            parse_mode='HTML'
                        )
                        
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
                    
                    # Inicializa lista de IDs se não existir
                    if 'ids_canal' not in context.user_data:
                        context.user_data['ids_canal'] = []
                    
                    # Adiciona o ID à lista (evita duplicatas)
                    if telegram_id not in context.user_data['ids_canal']:
                        context.user_data['ids_canal'].append(telegram_id)
                    
                    # Conta total de IDs
                    total_ids = len(context.user_data['ids_canal'])
                    
                    # Monta mensagem com lista de IDs
                    mensagem = f"✅ <b>Canal adicionado!</b>\n\n"
                    mensagem += f"📢 {nome_canal}\n"
                    mensagem += f"🆔 <code>{telegram_id}</code>\n"
                    mensagem += f"✅ Bot é admin\n\n"
                    mensagem += f"<b>IDs ({total_ids}):</b>\n"
                    
                    for i, canal_id in enumerate(context.user_data['ids_canal'], 1):
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
        for i, canal_id in enumerate(ids, 1):
            mensagem += f"{i}. <code>{canal_id}</code>\n"
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

def main():
    """Função principal para iniciar o bot"""
    # Cria a aplicação
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Adiciona handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Inicia o bot
    logger.info("Bot de vagas iniciado!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

