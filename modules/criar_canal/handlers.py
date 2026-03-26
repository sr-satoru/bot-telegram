import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from db_helpers import save_canal, get_all_canais, get_canal
import re

logger = logging.getLogger(__name__)

# --- Utilitários de Horário ---

def validar_horario(h):
    """Valida formato de horário (HH:MM em 24h)"""
    return bool(re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', h))

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

# --- Handlers ---

async def handle_criar_canal_callback(query, context):
    """Processa todos os callbacks relacionados à criação de canal"""
    data = query.data
    user_id = query.from_user.id

    if data == "criar_canal":
        # Inicia o fluxo de criação de canal
        context.user_data['criando_canal'] = True
        context.user_data['etapa'] = 'nome'
        await query.edit_message_text(
            "📢 <b>Criar Canal</b>\n\nEnvie o nome:",
            parse_mode='HTML'
        )
        return True

    elif data == "adicionar_outro_id":
        context.user_data['etapa'] = 'id'
        keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_adicionar_id")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📢 <b>Adicionar outro ID</b>\n\nEnvie outro ID do Telegram:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return True

    elif data == "cancelar_adicionar_id":
        nome_canal = context.user_data.get('nome_canal', 'N/A')
        ids_canal = context.user_data.get('ids_canal', [])
        if not ids_canal:
            await query.edit_message_text("⚠️ Nenhum ID adicionado.", parse_mode='HTML')
            return True
        total_ids = len(ids_canal)
        mensagem = f"✅ <b>Canal adicionado!</b>\n\n📢 {nome_canal}\n\n<b>IDs ({total_ids}):</b>\n"
        for i, canal_id in enumerate(ids_canal, 1):
            mensagem += f"{i}. <code>{canal_id}</code>\n"
        keyboard = [
            [InlineKeyboardButton("➕ Adicionar outro ID", callback_data="adicionar_outro_id")],
            [InlineKeyboardButton("✅ Confirmar", callback_data="confirmar_canal")]
        ]
        await query.edit_message_text(mensagem, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return True

    elif data == "confirmar_canal":
        context.user_data['etapa'] = 'horarios'
        context.user_data['horarios'] = []
        keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_criar_canal")]]
        await query.edit_message_text(
            "🕒 <b>Configurar Horários</b>\n\nEnvie os horários (formato 24h, separados por vírgula):\nEx: <code>08:00, 12:30</code>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return True

    elif data == "cancelar_criar_canal":
        # Limpa e volta
        for key in ['criando_canal', 'etapa', 'nome_canal', 'ids_canal', 'horarios']:
            context.user_data.pop(key, None)
        from bot_main_proxy import voltar_start_proxy # Precisaremos de um proxy ou import circular
        await voltar_start_proxy(query, context)
        return True

    elif data == "adicionar_horario":
        keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_adicionar_horario")]]
        await query.edit_message_text(
            "🕒 <b>Adicionar Horário</b>\n\nEnvie os horários (formato 24h, separados por vírgula):\nEx: <code>08:00, 12:30</code>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return True

    elif data == "cancelar_adicionar_horario":
        await mostrar_menu_horarios(query, context)
        return True

    elif data == "remover_horario":
        horarios = context.user_data.get('horarios', [])
        if not horarios:
            await query.edit_message_text("⚠️ Nenhum horário para remover.", parse_mode='HTML')
            return True
        keyboard = []
        for i, h in enumerate(sorted(horarios)):
            keyboard.append([InlineKeyboardButton(f"❌ {h}", callback_data=f"remove_horario_{i}")])
        keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_menu_horarios")])
        await query.edit_message_text("🗑 <b>Remover Horário</b>\n\nSelecione o horário:", 
                                     reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return True

    elif data.startswith("remove_horario_"):
        index = int(data.split("_")[-1])
        horarios = sorted(context.user_data.get('horarios', []))
        if 0 <= index < len(horarios):
            context.user_data['horarios'].remove(horarios[index])
            await mostrar_menu_horarios(query, context)
        return True

    elif data == "voltar_menu_horarios":
        await mostrar_menu_horarios(query, context)
        return True

    elif data == "confirmar_horarios":
        nome_canal = context.user_data.get('nome_canal')
        ids_canal = context.user_data.get('ids_canal', [])
        horarios = context.user_data.get('horarios', [])
        
        if not nome_canal or not ids_canal or not horarios:
            await query.answer("❌ Faltam dados para salvar o canal.", show_alert=True)
            return True
        
        canal_id = await save_canal(nome=nome_canal, user_id=user_id, ids_canal=ids_canal, horarios=horarios)
        
        # Limpa contexto
        for key in ['criando_canal', 'etapa', 'nome_canal', 'ids_canal', 'horarios']:
            context.user_data.pop(key, None)
            
        keyboard = [[InlineKeyboardButton("✅ Finalizar", callback_data="voltar_start")]]
        await query.edit_message_text(
            f"✅ <b>Canal criado com sucesso!</b>\n\n📢 {nome_canal}\n🆔 ID Interno: {canal_id}\n🕒 Horários: {len(horarios)}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return True

    return False

async def handle_criar_canal_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa o fluxo de mensagens durante a criação de canal"""
    message_text = update.message.text
    etapa = context.user_data.get('etapa')

    if etapa == 'nome':
        context.user_data['nome_canal'] = message_text
        context.user_data['etapa'] = 'id'
        context.user_data['ids_canal'] = []
        msg = await update.message.reply_text(f"✅ Nome: <b>{message_text}</b>\n\nEnvie o ID do canal:", parse_mode='HTML')
        return True

    elif etapa == 'id':
        try:
            telegram_id = int(message_text.strip())
            nome_canal = context.user_data.get('nome_canal', 'N/A')
            
            # Verificação básica de admin
            try:
                bot_member = await context.bot.get_chat_member(chat_id=telegram_id, user_id=context.bot.id)
                if bot_member.status not in ['administrator', 'creator']:
                    await update.message.reply_text(f"❌ Bot não é admin do canal <code>{telegram_id}</code>", parse_mode='HTML')
                    return True
                
                chat = await context.bot.get_chat(telegram_id)
                chat_title = chat.title or chat.username or f"Canal {telegram_id}"
                
                if telegram_id in context.user_data.get('ids_canal', []):
                    await update.message.reply_text("⚠️ ID já adicionado.", parse_mode='HTML')
                    return True
                
                context.user_data.setdefault('ids_canal', []).append(telegram_id)
                total_ids = len(context.user_data['ids_canal'])
                
                mensagem = f"✅ <b>Canal adicionado!</b>\n\n📢 {nome_canal}\n🆔 <code>{telegram_id}</code>\n📝 <b>Nome:</b> {chat_title}\n\n<b>IDs ({total_ids}):</b>\n"
                for i, cid in enumerate(context.user_data['ids_canal'], 1):
                    mensagem += f"{i}. <code>{cid}</code>\n"
                
                keyboard = [
                    [InlineKeyboardButton("➕ Adicionar outro ID", callback_data="adicionar_outro_id")],
                    [InlineKeyboardButton("✅ Confirmar", callback_data="confirmar_canal")]
                ]
                await update.message.reply_text(mensagem, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
            except Exception as e:
                await update.message.reply_text(f"❌ Erro ao verificar canal: {str(e)}", parse_mode='HTML')
        except ValueError:
            await update.message.reply_text("⚠️ ID inválido. Envie um número.", parse_mode='HTML')
        return True

    elif etapa == 'horarios':
        horarios_texto = message_text.strip()
        horarios_novos = [h.strip() for h in horarios_texto.split(",") if h.strip()]
        
        horarios_validos = [h for h in horarios_novos if validar_horario(h)]
        if len(horarios_validos) != len(horarios_novos):
            await update.message.reply_text("❌ Formato inválido. Use HH:MM, HH:MM", parse_mode='HTML')
            return True
        
        atuais = context.user_data.get('horarios', [])
        for h in horarios_validos:
            if h not in atuais: atuais.append(h)
        
        context.user_data['horarios'] = atuais
        msg = await update.message.reply_text("✅ Horários adicionados")
        await mostrar_menu_horarios_text(msg, context)
        return True

    return False
