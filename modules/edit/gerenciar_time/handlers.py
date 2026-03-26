from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from .utils import validar_horario, mostrar_painel_horarios

async def handle_edit_time_callback(query, context):
    """Handlers de callback para gerenciamento de horários na edição"""
    data = query.data
    dados = context.user_data.get('editando')
    if not dados: return False
    
    if data == "edit_horarios_menu" or data == "edit_adicionar_horario_cancelar":
        await mostrar_painel_horarios(query, context, is_edicao=True)
        return True
        
    elif data == "edit_adicionar_horario":
        dados['etapa'] = 'adicionando_horario'
        keyboard = [[InlineKeyboardButton("❌ Cancelar", callback_data="edit_adicionar_horario_cancelar")]]
        await query.edit_message_text(
            "🕒 <b>Adicionar Horário</b>\n\nEnvie os horários (formato 24h, separados por vírgula):\nEx: <code>08:00, 12:30</code>",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML'
        )
        return True
        
    elif data == "edit_remover_horario":
        horarios = dados.get('horarios', [])
        if not horarios:
            await query.answer("⚠️ Nenhum horário para remover.", show_alert=True)
            return True
        
        keyboard = [[InlineKeyboardButton(f"❌ {h}", callback_data=f"edit_remove_at_{i}")] for i, h in enumerate(sorted(horarios))]
        keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data="edit_horarios_menu")])
        await query.edit_message_text("🗑 <b>Remover Horário</b>\n\nSelecione:", 
                                     reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return True
        
    elif data.startswith("edit_remove_at_"):
        index = int(data.split("_")[-1])
        horarios = sorted(dados.get('horarios', []))
        if 0 <= index < len(horarios):
            dados['horarios'].remove(horarios[index])
            dados['changes_made'] = True
            await mostrar_painel_horarios(query, context, is_edicao=True)
        return True
        
    return False

async def handle_edit_time_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa entrada de texto para horários na edição"""
    dados = context.user_data.get('editando')
    if not dados or dados.get('etapa') != 'adicionando_horario': return False
        
    text = update.message.text.strip()
    novos = [h.strip() for h in text.split(",") if h.strip()]
    
    validos = [h for h in novos if validar_horario(h)]
    if len(validos) != len(novos):
        await update.message.reply_text("❌ Formato inválido. Use HH:MM, HH:MM")
        return True
    
    atuais = dados.get('horarios', [])
    for h in validos:
        if h not in atuais: atuais.append(h)
    
    dados['horarios'] = atuais
    dados['changes_made'] = True
    dados.pop('etapa', None)
    
    success_text = f"✅ {len(validos)} horário(s) processado(s)!\n\n"
    await mostrar_painel_horarios(update.message, context, is_edicao=True, extra_text=success_text)
    return True
