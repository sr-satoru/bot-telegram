from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from db_helpers import get_global_buttons, get_template_with_link_ids
from .utils import get_any_buttons, get_any_button_info

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

async def mostrar_menu_edicao_botao(obj, button_id, parent_id, owner_type='canal', texto_extra=""):
    """Menu para escolher o que editar no botão"""
    btn_info = await get_any_button_info(button_id, owner_type)
    if not btn_info: return
    
    label = "Global" if owner_type == 'canal' else "Fixo do Template"
    prefix = "global_button_tg" if owner_type == 'canal' else "fix_button_tg"
    
    mensagem = f"{texto_extra}\n" if texto_extra else ""
    mensagem += f"🛠️ <b>Configuração de Botão {label}</b>\n\n"
    mensagem += f"📝 <b>Texto:</b> {btn_info['text']}\n"
    mensagem += f"🔗 <b>Link:</b> {btn_info['url']}\n"
    if owner_type == 'template':
        status_icon = "🟢 ATIVO" if btn_info.get('status') == "ATIVO" else "🔴 INATIVO"
        mensagem += f"📊 <b>Status:</b> {status_icon}\n"
    
    keyboard = []
    # Opção de Toggle (apenas template)
    if owner_type == 'template':
        toggle_label = "🔴 Desativar" if btn_info.get('status') == "ATIVO" else "🟢 Ativar"
        keyboard.append([InlineKeyboardButton(toggle_label, callback_data=f"{prefix}_tgl_{button_id}")])
    
    keyboard.append([
        InlineKeyboardButton("✏️ Mudar Nome", callback_data=f"{prefix}_mt_{button_id}"),
        InlineKeyboardButton("🔗 Mudar Link", callback_data=f"{prefix}_mu_{button_id}")
    ])
    
    keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data=f"{prefix}_list_{parent_id}")])
    
    from telegram import CallbackQuery
    reply_markup = InlineKeyboardMarkup(keyboard)
    if isinstance(obj, CallbackQuery):
        await obj.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await obj.reply_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')

async def mostrar_prompt_texto_botao(obj, is_edit=False, text_atual=None, prefix="global_button_tg"):
    """Prompt para entrada do texto do botão"""
    if is_edit:
        mensagem = (
            "✏️ <b>Mudar Nome do Botão</b>\n\n"
            f"Nome atual: <code>{text_atual}</code>\n\n"
            "Envie o <b>novo nome</b> do botão:"
        )
    else:
        mensagem = (
            "🔘 <b>Adicionar Botão Inline</b>\n\n"
            "Envie o texto do botão:\n"
            "Ex: <code>Entrar no Grupo</code>"
        )
    
    # Botão de cancelar inline
    keyboard = [[InlineKeyboardButton("✖️ Cancelar", callback_data=f"{prefix}_cancel_prompt")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    from telegram import CallbackQuery
    if isinstance(obj, CallbackQuery):
        await obj.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await obj.reply_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')

async def mostrar_prompt_url_botao(obj, text_definido, prefix="global_button_tg", context=None):
    """Prompt para entrada da URL do botão"""
    mensagem = (
        f"✅ Texto definido: '{text_definido}'\n\n"
        "Agora envie a <b>URL</b> do botão:\n"
        "Ex: <code>https://t.me/meugrupo</code>"
    )
    # Tenta usar callback se disponível para ser mais limpo, mas aqui geralmente é resposta a mensagem
    keyboard = [[InlineKeyboardButton("✖️ Cancelar", callback_data=f"{prefix}_cancel_prompt")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    from telegram import CallbackQuery
    if isinstance(obj, CallbackQuery):
        await obj.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await obj.reply_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')

async def mostrar_confirmacao_delecao(query, button_id, button_text, owner_type='canal'):
    """Gera menu de confirmação para deletar um botão"""
    prefix = "global_button_tg" if owner_type == 'canal' else "fix_button_tg"
    label = "Global" if owner_type == 'canal' else "do Template"
    mensagem = (
        "⚠️ <b>Confirmar Deleção</b>\n\n"
        f"Tem certeza que deseja deletar o botão {label} <b>'{button_text}'</b>?"
    )
    keyboard = [[
        InlineKeyboardButton("✅ Confirmar", callback_data=f"{prefix}_cdel_{button_id}"),
        InlineKeyboardButton("❌ Cancelar", callback_data=f"{prefix}_cancel_prompt")
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
