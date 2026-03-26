import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

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

async def handle_edit_time_callback(query, context):
    """Handlers de callback para gerenciamento de horários"""
    data = query.data
    
    if data == "edit_horarios_menu":
        await mostrar_menu_horarios_edicao(query, context)
        return True
        
    elif data == "edit_add_horario":
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
        return True
        
    elif data == "edit_remove_horario":
        # Mostra lista de horários para remover
        dados = context.user_data.get('editando', {})
        horarios = dados.get('horarios', [])
        
        if not horarios:
            await query.edit_message_text(
                "⚠️ Nenhum horário para remover.",
                parse_mode='HTML'
            )
            return True
        
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
        return True
        
    elif data.startswith("edit_remove_horario_"):
        # Remove um horário específico
        index = int(data.split("_")[-1])
        dados = context.user_data.get('editando', {})
        horarios = dados.get('horarios', [])
        horarios_ordenados = sorted(horarios)
        
        if 0 <= index < len(horarios_ordenados):
            horario_removido = horarios_ordenados[index]
            horarios.remove(horario_removido)
            dados['horarios'] = horarios
            dados['changes_made'] = True
            
            await mostrar_menu_horarios_edicao(query, context)
        return True
        
    return False

async def handle_edit_time_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa horários enviados pelo usuário"""
    if 'editando' not in context.user_data:
        return False
        
    dados = context.user_data['editando']
    etapa = dados.get('etapa')
    
    if etapa == 'adicionando_horario':
        message_text = update.message.text
        # Adiciona novos horários
        horarios_texto = message_text.strip()
        horarios_novos = [h.strip() for h in horarios_texto.split(",") if h.strip()]
        
        if not horarios_novos:
            await update.message.reply_text(
                "⚠️ Nenhum horário informado.",
                parse_mode='HTML'
            )
            return True
        
        # Valida horários
        horarios_validos = []
        horarios_invalidos = []
        
        for h in horarios_novos:
            if re.match(r"^(2[0-3]|[01]?\d):[0-5]\d$", h):
                horarios_validos.append(h)
            else:
                horarios_invalidos.append(h)
        
        if horarios_invalidos:
            await update.message.reply_text(
                f"❌ Horário(s) inválido(s): {', '.join(horarios_invalidos)}",
                parse_mode='HTML'
            )
            return True
        
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
        
        # Envia mensagem
        await update.message.reply_text(
            f"✅ {len(horarios_adicionados)} horário(s) adicionado(s)!",
            parse_mode='HTML'
        )
        
        # Mostra menu de horários
        mensagem = "🕒 <b>Gerenciar Horários</b>\n\n"
        if horarios_atuais:
            mensagem += "<b>Horários configurados:</b>\n"
            for i, horario in enumerate(sorted(horarios_atuais), 1):
                mensagem += f"{i}. <code>{horario}</code>\n"
        
        keyboard = [
            [InlineKeyboardButton("➕ Adicionar Horário", callback_data="edit_add_horario")],
            [InlineKeyboardButton("🗑 Remover Horário", callback_data="edit_remove_horario")],
            [InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
        return True
        
    return False
