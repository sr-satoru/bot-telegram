from .ui import (
    mostrar_menu_botoes, mostrar_prompt_texto_botao, 
    mostrar_prompt_url_botao, mostrar_confirmacao_delecao, 
    notificar_sucesso
)
from .utils import (
    get_any_buttons, save_any_buttons, delete_any_button, get_any_button_info
)

async def handle_any_button_callback(query, context, owner_type='canal'):
    """Router genérico para callbacks de botões (canal ou template)"""
    data = query.data
    prefix = "global" if owner_type == 'canal' else "template"
    
    # Suporte a prefixos alternativos (ex: inline_button vindo da UI antiga de template)
    if owner_type == 'template' and "inline_button" in data:
        data = data.replace("inline_button", "template_button")

    if data == f"edit_{prefix}_buttons":
        # Conserta busca de parent_id para canal (pode estar em 'id' ou 'canal_id')
        if owner_type == 'canal':
            edit_data = context.user_data.get('editando', {})
            parent_id = edit_data.get('canal_id') or edit_data.get('id')
        else:
            parent_id = context.user_data.get('editing_template_id')
            
        if not parent_id: return True
        await mostrar_menu_botoes(query, parent_id, owner_type)
        return True
        
    elif data.startswith(f"adicionar_{prefix}_button_"):
        parent_id = int(data.split("_")[-1])
        context.user_data['adicionando_button'] = True
        context.user_data['button_parent_id'] = parent_id
        context.user_data['button_owner_type'] = owner_type
        context.user_data['button_etapa'] = 'texto'
        await mostrar_prompt_texto_botao(query, is_edit=False)
        return True
        
    elif data.startswith(f"edit_{prefix}_button_"):
        button_id = int(data.split("_")[-1])
        btn_info = await get_any_button_info(button_id, owner_type)
        if not btn_info: return True
            
        context.user_data['editando_button'] = True
        context.user_data['button_id'] = button_id
        context.user_data['button_parent_id'] = btn_info.get('canal_id') or btn_info.get('template_id')
        context.user_data['button_owner_type'] = owner_type
        context.user_data['button_etapa'] = 'texto'
        await mostrar_prompt_texto_botao(query, is_edit=True, text_atual=btn_info['text'], url_atual=btn_info['url'])
        return True
        
    elif data.startswith(f"deletar_{prefix}_button_"):
        button_id = int(data.split("_")[-1])
        btn_info = await get_any_button_info(button_id, owner_type)
        if btn_info:
            await mostrar_confirmacao_delecao(query, button_id, btn_info['text'], owner_type)
        return True
        
    elif data.startswith(f"confirmar_deletar_{prefix}_button_"):
        button_id = int(data.split("_")[-1])
        btn_info = await get_any_button_info(button_id, owner_type)
        if not btn_info: return True
            
        parent_id = btn_info.get('canal_id') or btn_info.get('template_id')
        await delete_any_button(button_id, owner_type)
        await mostrar_menu_botoes(query, parent_id, owner_type, "✅ Botão deletado!")
        return True

    elif data.startswith("cancelar_delecao_"):
        # Extrai o owner_type do callback data se possível, ou usa o padrão
        if owner_type == 'canal':
            edit_data = context.user_data.get('editando', {})
            parent_id = edit_data.get('canal_id') or edit_data.get('id')
        else:
            parent_id = context.user_data.get('editing_template_id')
            
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
        parent_id = user_data.get('button_parent_id')
        owner_type = user_data.get('button_owner_type', 'canal')
        
        # Limpa contexto genérico
        params = ['adicionando_button', 'editando_button', 'button_parent_id', 
                  'button_owner_type', 'button_etapa', 'button_text', 'button_id']
        for key in params: user_data.pop(key, None)
        
        if parent_id:
            await mostrar_menu_botoes(message, parent_id, owner_type, texto_extra="❌ Operação cancelada.")
        else:
            await notificar_sucesso(message, "cancelado")
        return True

    # Fluxo unificado de ADICIONAR/EDITAR
    is_adding = user_data.get('adicionando_button')
    is_editing = user_data.get('editando_button')
    
    if is_adding or is_editing:
        etapa = user_data.get('button_etapa')
        parent_id = user_data.get('button_parent_id')
        owner_type = user_data.get('button_owner_type', 'canal')
        
        if etapa == 'texto':
            user_data['button_text'] = text
            user_data['button_etapa'] = 'url'
            await mostrar_prompt_url_botao(message, text)
            return True
            
        elif etapa == 'url':
            url = text
            button_text = user_data.get('button_text')
            
            # Busca lista atual
            current_buttons = await get_any_buttons(parent_id, owner_type)
            
            if is_adding:
                updated_list = [(b['text'], b['url']) for b in current_buttons]
                updated_list.append((button_text, url))
                msg_type = "adicionado"
            else:
                bid = user_data.get('button_id')
                updated_list = []
                for b in current_buttons:
                    if b['id'] == bid:
                        updated_list.append((button_text, url))
                    else:
                        updated_list.append((b['text'], b['url']))
                msg_type = "editado"
            
            await save_any_buttons(parent_id, updated_list, owner_type)
            
            # Limpa contexto
            params = ['adicionando_button', 'editando_button', 'button_parent_id', 
                      'button_owner_type', 'button_etapa', 'button_text', 'button_id']
            for key in params: user_data.pop(key, None)
            
            # Mostra o menu de volta (passando a mensagem para usar reply_text)
            sucesso_msg = f"✅ Botão {msg_type} com sucesso!"
            await mostrar_menu_botoes(message, parent_id, owner_type, texto_extra=sucesso_msg)
            return True
            
    return False

# Retrocompatibilidade
async def handle_global_button_message(update, context):
    return await handle_any_button_message(update, context)
