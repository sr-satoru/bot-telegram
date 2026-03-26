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
        # Atualiza o nome e gera feedback
        dados['nome'] = message_text
        dados['changes_made'] = True
        del dados['etapa']
        
        from modules.ui import mostrar_menu_edicao
        success_text = f"✅ <b>Nome atualizado com sucesso!</b>\n\n"
        await mostrar_menu_edicao(update.message, context, extra_text=success_text)
        return True
        
    return False
