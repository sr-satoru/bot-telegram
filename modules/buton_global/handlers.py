from .ui import (
    mostrar_menu_botoes, mostrar_prompt_texto_botao, 
    mostrar_prompt_url_botao, mostrar_confirmacao_delecao, 
    notificar_sucesso, mostrar_menu_edicao_botao
)
from .utils import (
    get_any_buttons, save_any_buttons, delete_any_button, get_any_button_info, update_any_button
)
from db_helpers import toggle_inline_button_status
from telegram import MessageEntity

async def handle_any_button_callback(query, context, owner_type='canal'):
    """Router genérico para callbacks de botões (canal ou template)"""
    data = query.data
    prefix = "global_button_tg" if owner_type == 'canal' else "fix_button_tg"
    
    # Suporte a prefixos legados (opcional, mas bom para transição rápida se houver mensagens antigas)
    if "template_button_" in data: data = data.replace("template_button_", "fix_button_tg_")
    if "inline_button_" in data: data = data.replace("inline_button_", "fix_button_tg_")
    if "global_button_" in data and "global_button_tg" not in data: data = data.replace("global_button_", "global_button_tg_")

    if data.startswith(f"{prefix}_list_") or data == "edit_template_buttons":
        # Nota: 'edit_template_buttons' é o callback que vem do menu de template
        if "_" in data and data.split("_")[-1].isdigit():
            parent_id = int(data.split("_")[-1])
        else:
            # Fallback para user_data se o ID não estiver no callback
            if owner_type == 'canal':
                edit_data = context.user_data.get('editando', {})
                parent_id = edit_data.get('canal_id') or edit_data.get('id')
            else:
                parent_id = context.user_data.get('editing_template_id')
                
        if not parent_id: return True
        # Limpa estados de edição ao voltar para a lista
        for key in ['adicionando_button', 'editando_button', 'button_id', 'button_etapa', 'button_field']: 
            context.user_data.pop(key, None)
            
        await mostrar_menu_botoes(query, parent_id, owner_type)
        return True
        
    elif data.startswith(f"{prefix}_add_"):
        parent_id = int(data.split("_")[-1])
        context.user_data['adicionando_button'] = True
        context.user_data['button_parent_id'] = parent_id
        context.user_data['button_owner_type'] = owner_type
        context.user_data['button_etapa'] = 'texto'
        await mostrar_prompt_texto_botao(query, is_edit=False, prefix=prefix)
        return True
        
    elif data.startswith(f"{prefix}_edit_"):
        button_id = int(data.split("_")[-1])
        btn_info = await get_any_button_info(button_id, owner_type)
        if not btn_info: return True
        
        parent_id = btn_info.get('canal_id') or btn_info.get('template_id')
        await mostrar_menu_edicao_botao(query, button_id, parent_id, owner_type)
        return True

    elif data.startswith(f"{prefix}_mt_"):
        button_id = int(data.split("_")[-1])
        btn_info = await get_any_button_info(button_id, owner_type)
        if not btn_info: return True
        
        context.user_data['editando_button'] = True
        context.user_data['button_id'] = button_id
        context.user_data['button_owner_type'] = owner_type
        context.user_data['button_etapa'] = 'texto'
        context.user_data['button_field'] = 'text'
        await mostrar_prompt_texto_botao(query, is_edit=True, text_atual=btn_info['text'], prefix=prefix)
        return True

    elif data.startswith(f"{prefix}_mu_"):
        button_id = int(data.split("_")[-1])
        btn_info = await get_any_button_info(button_id, owner_type)
        if not btn_info: return True
        
        context.user_data['editando_button'] = True
        context.user_data['button_id'] = button_id
        context.user_data['button_owner_type'] = owner_type
        context.user_data['button_etapa'] = 'url'
        context.user_data['button_field'] = 'url'
        await mostrar_prompt_url_botao(query, btn_info['text'], prefix=prefix, context=context)
        return True
        
    elif data.startswith(f"{prefix}_del_"):
        button_id = int(data.split("_")[-1])
        btn_info = await get_any_button_info(button_id, owner_type)
        if btn_info:
            await mostrar_confirmacao_delecao(query, button_id, btn_info['text'], owner_type)
        return True
        
    elif data.startswith(f"{prefix}_cdel_"):
        button_id = int(data.split("_")[-1])
        btn_info = await get_any_button_info(button_id, owner_type)
        if not btn_info: return True
            
        parent_id = btn_info.get('canal_id') or btn_info.get('template_id')
        await delete_any_button(button_id, owner_type)
        await mostrar_menu_botoes(query, parent_id, owner_type, "✅ Botão deletado!")
        return True

    elif data.startswith(f"{prefix}_tgl_"):
        button_id = int(data.split("_")[-1])
        if owner_type == 'template':
            new_status = await toggle_inline_button_status(button_id)
            btn_info = await get_any_button_info(button_id, owner_type)
            parent_id = btn_info.get('template_id')
            label = "ativado" if new_status == "ATIVO" else "desativado"
            # Se já estávamos no menu de edição, volta para ele com o status novo
            await mostrar_menu_edicao_botao(query, button_id, parent_id, owner_type, f"✅ Botão {label}!")
        return True

    elif data.startswith(f"{prefix}_cancel_prompt") or data == "cancelar_delecao_":
        # Extrai IDs se possível
        btn_id = context.user_data.get('button_id')
        parent_id = context.user_data.get('button_parent_id')
        
        if not parent_id:
            if owner_type == 'canal':
                edit_data = context.user_data.get('editando', {})
                parent_id = edit_data.get('canal_id') or edit_data.get('id')
            else:
                parent_id = context.user_data.get('editing_template_id')
        
        # Limpa estados
        for key in ['adicionando_button', 'editando_button', 'button_id', 'button_etapa', 'button_field']: 
            context.user_data.pop(key, None)

        if btn_id:
            # Se estava editando um botão, volta para o menu dele
            await mostrar_menu_edicao_botao(query, btn_id, parent_id, owner_type)
        else:
            # Se estava adicionando ou deletando, volta para a lista
            await mostrar_menu_botoes(query, parent_id, owner_type)
        return True
        
    return False

# Retrocompatibilidade e routers específicos
async def handle_global_button_callback(query, context):
    return await handle_any_button_callback(query, context, owner_type='canal')

async def handle_template_button_callback(query, context):
    return await handle_any_button_callback(query, context, owner_type='template')

async def handle_any_button_message(update, context):
    """Router genérico para mensagens de botões (canal ou template)"""
    user_data = context.user_data
    message = update.message
    text = message.text
    if text == "/cancelar":
        # Recupera dados para voltar ao menu
        btn_id = user_data.get('button_id')
        parent_id = user_data.get('button_parent_id')
        owner_type = user_data.get('button_owner_type', 'canal')
        
        # Limpa contexto genérico
        params = ['adicionando_button', 'editando_button', 'button_parent_id', 
                  'button_owner_type', 'button_etapa', 'button_text', 'button_id', 'button_field']
        for key in params: user_data.pop(key, None)
        
        if btn_id and parent_id:
            await mostrar_menu_edicao_botao(message, btn_id, parent_id, owner_type, texto_extra="❌ Operação cancelada.")
        elif parent_id:
            await mostrar_menu_botoes(message, parent_id, owner_type, texto_extra="❌ Operação cancelada.")
        else:
            await notificar_sucesso(message, "cancelado")
            
        # Limpa dados temporários
        user_data.pop('pending_emoji_id', None)
        return True

    # Fluxo unificado de ADICIONAR/EDITAR
    is_adding = user_data.get('adicionando_button')
    is_editing = user_data.get('editando_button')
    
    if is_adding or is_editing:
        etapa = user_data.get('button_etapa')
        parent_id = user_data.get('button_parent_id')
        owner_type = user_data.get('button_owner_type', 'canal')
        
        # --- FLUXO DE EDIÇÃO ---
        if is_editing:
            button_id = user_data.get('button_id')
            field = user_data.get('button_field')
            
            if field == 'text':
                # Extração e validação de emoji premium para o ícone
                entities = message.entities or message.caption_entities or []
                custom_emojis = [e for e in entities if e.type == MessageEntity.CUSTOM_EMOJI]
                
                if len(custom_emojis) > 1:
                    await message.reply_text("❌ Só é permitido <b>1 emoji premium</b> por botão.\nRemova os extras e tente novamente.", parse_mode='HTML')
                    return True
                
                emoji_id = None
                if custom_emojis:
                    ent = custom_emojis[0]
                    emoji_id = ent.custom_emoji_id
                    # Limpa o emoji do texto (UTF-16 safe)
                    t_utf16 = text.encode('utf-16-le')
                    text = (t_utf16[:ent.offset*2] + t_utf16[(ent.offset+ent.length)*2:]).decode('utf-16-le').strip()
                
                await update_any_button(button_id, {"text": text, "icon_emoji_id": emoji_id}, owner_type)
                user_data.pop('button_etapa', None)
                user_data.pop('button_field', None)
                user_data.pop('editando_button', None)
                await mostrar_menu_edicao_botao(message, button_id, parent_id, owner_type, "✅ Nome do botão atualizado!")
                return True
                
            elif field == 'url':
                if not text.startswith(('http', 'https')):
                    await message.reply_text("❌ URL inválida. Envie um link começando com http:// ou https://")
                    return True
                await update_any_button(button_id, {"url": text}, owner_type)
                user_data.pop('button_etapa', None)
                user_data.pop('button_field', None)
                user_data.pop('editando_button', None)
                await mostrar_menu_edicao_botao(message, button_id, parent_id, owner_type, "✅ Link do botão atualizado!")
                return True
        
        # --- FLUXO DE ADIÇÃO (EXISTENTE) ---
        if etapa == 'texto':
            # Extração e validação de emoji premium para o ícone
            entities = message.entities or message.caption_entities or []
            custom_emojis = [e for e in entities if e.type == MessageEntity.CUSTOM_EMOJI]
            
            if len(custom_emojis) > 1:
                await message.reply_text("❌ Só é permitido <b>1 emoji premium</b> por botão.\nRemova os extras e tente novamente.", parse_mode='HTML')
                return True
            
            emoji_id = None
            if custom_emojis:
                ent = custom_emojis[0]
                emoji_id = ent.custom_emoji_id
                # Limpa o emoji do texto (UTF-16 safe)
                t_utf16 = text.encode('utf-16-le')
                text = (t_utf16[:ent.offset*2] + t_utf16[(ent.offset+ent.length)*2:]).decode('utf-16-le').strip()
            
            user_data['button_text'] = text
            user_data['pending_emoji_id'] = emoji_id
            user_data['button_etapa'] = 'url'
            prefix = "global_button_tg" if owner_type == 'canal' else "fix_button_tg"
            await mostrar_prompt_url_botao(message, text, prefix=prefix, context=context)
            return True
            
        elif etapa == 'url':
            if not text.startswith(('http', 'https')):
                await message.reply_text("❌ URL inválida. Envie um link começando com http:// ou https://")
                return True
                
            button_text = user_data.get('button_text')
            emoji_id = user_data.get('pending_emoji_id')
            url = text
            
            # Busca lista atual para adicionar à ela
            current_buttons = await get_any_buttons(parent_id, owner_type)
            # Lista de tuplas (text, url, icon_emoji_id)
            updated_list = [(b['text'], b['url'], b.get('icon_emoji_id')) for b in current_buttons]
            updated_list.append((button_text, url, emoji_id))
            
            await save_any_buttons(parent_id, updated_list, owner_type)
            
            # Limpa tudo
            params = ['adicionando_button', 'button_parent_id', 'button_owner_type', 
                      'button_etapa', 'button_text', 'pending_emoji_id']
            for key in params: user_data.pop(key, None)
            
            await mostrar_menu_botoes(message, parent_id, owner_type, texto_extra="✅ Botão adicionado!")
            return True
        
    return False

# Retrocompatibilidade
async def handle_global_button_message(update, context):
    return await handle_any_button_message(update, context)
