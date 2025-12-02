import os
import re
import logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from database import Database

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

# Inicializa banco de dados
db = Database()

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
            
            mensagem = f"✅ <b>Configuração salva!</b>\n\n"
            mensagem += f"📢 {nome_canal}\n"
            mensagem += f"🆔 IDs ({len(ids_canal)}):\n"
            for i, canal_id_telegram in enumerate(ids_canal, 1):
                mensagem += f"{i}. <code>{canal_id_telegram}</code>\n"
            mensagem += f"\n🕒 Horários ({len(horarios)}):\n"
            for i, horario in enumerate(sorted(horarios), 1):
                mensagem += f"{i}. {horario}\n"
            mensagem += f"\n💾 ID do canal: {canal_id}"
            
        except Exception as e:
            logger.error(f"Erro ao salvar canal: {e}")
            mensagem = f"❌ Erro ao salvar no banco de dados: {str(e)}"
        
        # Limpa o contexto
        del context.user_data['criando_canal']
        del context.user_data['etapa']
        del context.user_data['nome_canal']
        del context.user_data['ids_canal']
        del context.user_data['horarios']
        
        await query.edit_message_text(mensagem, parse_mode='HTML')
    

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para mensagens de texto"""
    message_text = update.message.text
    
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

