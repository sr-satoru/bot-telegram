from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from db_helpers import get_global_buttons

async def mostrar_menu_botoes_globais(query, canal_id, texto_extra=""):
    """Mostra o menu de gerenciamento de botões globais do canal"""
    global_buttons = await get_global_buttons(canal_id)
    
    mensagem = f"{texto_extra}\n" if texto_extra else ""
    mensagem += "🔘 <b>Botões Globais</b>\n\n"
    mensagem += "Botões globais são aplicados a <b>TODOS</b> os templates do canal.\n\n"
    
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
            InlineKeyboardButton(f"✏️ {button_display}", callback_data=f"edit_global_button_{button['id']}"),
            InlineKeyboardButton("🗑️", callback_data=f"deletar_global_button_{button['id']}")
        ])
    
    keyboard.append([InlineKeyboardButton("➕ Adicionar Botão Global", callback_data=f"adicionar_global_button_{canal_id}")])
    keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar")])
    
    await query.edit_message_text(mensagem, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def mostrar_prompt_texto_botao(query, is_edit=False, text_atual=None, url_atual=None):
    """Prompt para entrada do texto do botão"""
    if is_edit:
        mensagem = (
            f"✏️ <b>Editar Botão Global</b>\n\n"
            f"Texto atual: '{text_atual}'\n"
            f"URL atual: {url_atual}\n\n"
            "Envie o <b>novo texto</b> do botão (ou /cancelar):"
        )
    else:
        mensagem = (
            "🔘 <b>Adicionar Botão Global</b>\n\n"
            "Envie o texto do botão:\n"
            "Ex: <code>Entrar no Grupo</code>"
        )
    await query.edit_message_text(mensagem, parse_mode='HTML')

async def mostrar_prompt_url_botao(message, text_definido):
    """Prompt para entrada da URL do botão"""
    mensagem = (
        f"✅ Texto definido: '{text_definido}'\n\n"
        "Agora envie a <b>URL</b> do botão:\n"
        "Ex: <code>https://t.me/meugrupo</code>"
    )
    await message.reply_text(mensagem, parse_mode='HTML')

async def mostrar_confirmacao_delecao(query, button_id, button_text):
    """Gera menu de confirmação para deletar um botão global"""
    mensagem = (
        "⚠️ <b>Confirmar Deleção</b>\n\n"
        f"Tem certeza que deseja deletar o botão global <b>'{button_text}'</b>?"
    )
    keyboard = [[
        InlineKeyboardButton("✅ Confirmar", callback_data=f"confirmar_deletar_global_button_{button_id}"),
        InlineKeyboardButton("❌ Cancelar", callback_data="edit_global_buttons")
    ]]
    await query.edit_message_text(mensagem, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def notificar_sucesso(message, acao="adicionado"):
    """Notifica sucesso em uma operação"""
    msjs = {
        "adicionado": "✅ Botão global adicionado com sucesso!",
        "editado": "✅ Botão global atualizado com sucesso!",
        "deletado": "✅ Botão global deletado!",
        "cancelado": "❌ Operação cancelada."
    }
    await message.reply_text(msjs.get(acao, "✅ Operação concluída!"), parse_mode='HTML')
