import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def validar_horario(h):
    """Valida formato de horário (HH:MM em 24h)"""
    return bool(re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', h))

async def mostrar_painel_horarios(obj, context, is_edicao=False, extra_text=""):
    """
    Função unificada para mostrar o painel de horários.
    obj: Pode ser um CallbackQuery ou Message
    """
    if is_edicao:
        dados = context.user_data.get('editando', {})
        horarios = dados.get('horarios', [])
        prefix = "edit_"
    else:
        horarios = context.user_data.get('horarios', [])
        prefix = ""

    mensagem = extra_text or "🕒 <b>Gerenciar Horários</b>\n\n"
    if extra_text and "Horários" not in extra_text:
        mensagem += "🕒 <b>Gerenciar Horários</b>\n\n"
    
    if horarios:
        mensagem += "<b>Horários configurados:</b>\n"
        for i, horario in enumerate(sorted(horarios), 1):
            mensagem += f"{i}. <code>{horario}</code>\n"
    else:
        mensagem += "❌ Nenhum horário configurado\n"
    
    mensagem += f"\nTotal: {len(horarios)} horário(s)"
    
    # Callbacks mudam dependendo do contexto (criação vs edição)
    keyboard = [
        [
            InlineKeyboardButton("➕ Adicionar Horário", callback_data=f"{prefix}adicionar_horario"),
        ],
    ]
    
    if horarios:
        keyboard.append([
            InlineKeyboardButton("🗑 Remover Horário", callback_data=f"{prefix}remover_horario"),
        ])
    
    # No fluxo de criação o botão é 'Confirmar', na edição é 'Voltar' (pois o salvar é global)
    if is_edicao:
        keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar")])
    else:
        keyboard.append([InlineKeyboardButton("✅ Confirmar", callback_data="confirmar_horarios")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    from telegram import CallbackQuery
    
    if isinstance(obj, CallbackQuery):
        await obj.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    else:
        # Se for Message (seja do usuário ou do bot), usamos reply_text para garantir nova mensagem
        # ou poderíamos tentar edit_text se fosse do bot, mas reply_text é mais seguro para o fluxo planejado
        await obj.reply_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
