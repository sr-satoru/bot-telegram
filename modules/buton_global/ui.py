from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from db_helpers import get_global_buttons, get_template_with_link_ids
from .utils import get_any_buttons

async def mostrar_menu_botoes(obj, parent_id, owner_type='canal', texto_extra=""):
    """Mostra o menu de gerenciamento de botões (canal ou template)"""
    buttons = await get_any_buttons(parent_id, owner_type)
    
    label = "Globais" if owner_type == 'canal' else "do Template"
    mensagem = f"{texto_extra}\n" if texto_extra else ""
    mensagem += f"🔘 <b>Botões {label}</b>\n\n"
    if owner_type == 'canal':
        mensagem += "Botões globais são aplicados a <b>TODOS</b> os templates do canal.\n\n"
    
    if buttons:
        mensagem += f"<b>Botões configurados ({len(buttons)}):</b>\n"
        for i, button in enumerate(buttons, 1):
            url_display = button['url'] if len(button['url']) <= 40 else button['url'][:37] + "..."
            status_icon = "🟢" if button.get('status') == "ATIVO" else "🔴"
            status_text = f" ({status_icon})" if owner_type == 'template' else ""
            mensagem += f"{i}. '{button['text']}'{status_text}\n   → {url_display}\n\n"
    else:
        mensagem += f"❌ Nenhum botão {label.lower()} configurado\n\n"
    
    keyboard = []
    prefix = "global_button_tg" if owner_type == 'canal' else "fix_button_tg"
    
    for button in buttons:
        button_display = button['text'][:25] + "..." if len(button['text']) > 25 else button['text']
        
        row = [
            InlineKeyboardButton(f"✏️ {button_display}", callback_data=f"{prefix}_edit_{button['id']}"),
        ]
        
        if owner_type == 'template':
            toggle_label = "🔴 Desativar" if button.get('status') == "ATIVO" else "🟢 Ativar"
            row.append(InlineKeyboardButton(toggle_label, callback_data=f"{prefix}_tgl_{button['id']}"))
            
        row.append(InlineKeyboardButton("🗑️", callback_data=f"{prefix}_del_{button['id']}"))
        keyboard.append(row)
    
    add_label = "Botão Global" if owner_type == 'canal' else "Botão no Template"
    keyboard.append([InlineKeyboardButton(f"➕ Adicionar {add_label}", callback_data=f"{prefix}_add_{parent_id}")])
    
    back_data = "edit_voltar" if owner_type == 'canal' else f"edit_template_{parent_id}"
    keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data=back_data)])
    
    from telegram import CallbackQuery
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if isinstance(obj, CallbackQuery):
        await obj.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await obj.reply_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')

async def mostrar_prompt_texto_botao(query, is_edit=False, text_atual=None, url_atual=None):
    """Prompt para entrada do texto do botão"""
    label = "Botão Inline"
    if is_edit:
        mensagem = (
            f"✏️ <b>Editar {label}</b>\n\n"
            f"Texto atual: '{text_atual}'\n"
            f"URL atual: {url_atual}\n\n"
            "Envie o <b>novo texto</b> do botão (ou /cancelar):"
        )
    else:
        mensagem = (
            f"🔘 <b>Adicionar {label}</b>\n\n"
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

async def mostrar_confirmacao_delecao(query, button_id, button_text, owner_type='canal'):
    """Gera menu de confirmação para deletar um botão"""
    prefix = "global" if owner_type == 'canal' else "template"
    label = "Global" if owner_type == 'canal' else "do Template"
    mensagem = (
        "⚠️ <b>Confirmar Deleção</b>\n\n"
        f"Tem certeza que deseja deletar o botão {label} <b>'{button_text}'</b>?"
    )
    keyboard = [[
        InlineKeyboardButton("✅ Confirmar", callback_data=f"confirmar_deletar_{prefix}_button_{button_id}"),
        InlineKeyboardButton("❌ Cancelar", callback_data=f"cancelar_delecao_{prefix}")
    ]]
    await query.edit_message_text(mensagem, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def notificar_sucesso(message, acao="adicionado", owner_type='canal'):
    """Notifica sucesso em uma operação"""
    label = "global" if owner_type == 'canal' else "do template"
    msjs = {
        "adicionado": f"✅ Botão {label} adicionado com sucesso!",
        "editado": f"✅ Botão {label} atualizado com sucesso!",
        "deletado": f"✅ Botão {label} deletado!",
        "cancelado": "❌ Operação cancelada."
    }
    await message.reply_text(msjs.get(acao, "✅ Operação concluída!"), parse_mode='HTML')
