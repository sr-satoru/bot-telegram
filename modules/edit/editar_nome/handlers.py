from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

async def handle_edit_nome_callback(query, context):
    """Inicia o fluxo de edição de nome"""
    if query.data == "edit_nome":
        # Inicia edição do nome
        context.user_data['editando']['etapa'] = 'editando_nome'
        nome_atual = context.user_data['editando']['nome']
        
        await query.edit_message_text(
            f"📛 <b>Editar Nome</b>\n\nNome atual: <b>{nome_atual}</b>\n\nEnvie o novo nome:",
            parse_mode='HTML'
        )
        return True
    return False

async def handle_edit_nome_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa o novo nome enviado pelo usuário"""
    if 'editando' not in context.user_data:
        return False
        
    dados = context.user_data['editando']
    etapa = dados.get('etapa')
    
    if etapa == 'editando_nome':
        message_text = update.message.text
        # Atualiza o nome
        dados['nome'] = message_text
        dados['changes_made'] = True
        del dados['etapa']
        
        # Envia mensagem curta
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
        return True
        
    return False
