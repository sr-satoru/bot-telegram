from db_helpers import (
    get_global_buttons, save_global_buttons, delete_global_button, 
    get_global_button_info
)
from .ui import (
    mostrar_menu_botoes_globais, mostrar_prompt_texto_botao, 
    mostrar_prompt_url_botao, mostrar_confirmacao_delecao, 
    notificar_sucesso
)

async def handle_global_button_callback(query, context):
    """Router para callbacks de botões globais"""
    
    if query.data == "edit_global_buttons":
        dados = context.user_data.get('editando')
        if not dados:
            await query.answer("❌ Sessão expirada.")
            return True
        await mostrar_menu_botoes_globais(query, dados['id'])
        return True
        
    elif query.data.startswith("adicionar_global_button_"):
        canal_id = int(query.data.split("_")[-1])
        context.user_data['adicionando_global_button'] = True
        context.user_data['global_button_canal_id'] = canal_id
        context.user_data['global_button_etapa'] = 'texto'
        
        await mostrar_prompt_texto_botao(query, is_edit=False)
        return True
        
    elif query.data.startswith("edit_global_button_"):
        button_id = int(query.data.split("_")[-1])
        btn_info = await get_global_button_info(button_id)
        
        if not btn_info:
            await query.answer("❌ Botão não encontrado.")
            return True
            
        context.user_data['editando_global_button'] = True
        context.user_data['global_button_id'] = button_id
        context.user_data['global_button_canal_id'] = btn_info['canal_id']
        context.user_data['global_button_etapa'] = 'texto'
        
        await mostrar_prompt_texto_botao(query, is_edit=True, text_atual=btn_info['text'], url_atual=btn_info['url'])
        return True
        
    elif query.data.startswith("deletar_global_button_"):
        button_id = int(query.data.split("_")[-1])
        btn_info = await get_global_button_info(button_id)
        if btn_info:
            await mostrar_confirmacao_delecao(query, button_id, btn_info['text'])
        return True
        
    elif query.data.startswith("confirmar_deletar_global_button_"):
        button_id = int(query.data.split("_")[-1])
        btn_info = await get_global_button_info(button_id)
        if not btn_info:
            await query.answer("❌ Botão não encontrado.")
            return True
            
        canal_id = btn_info['canal_id']
        await delete_global_button(button_id)
        # Tenta notificar mas voltando ao menu
        await mostrar_menu_botoes_globais(query, canal_id, "✅ Botão deletado!")
        return True
        
    return False

async def handle_global_button_message(update, context):
    """Router para mensagens (entrada de texto/url) de botões globais"""
    message = update.message
    text = message.text
    
    # Se cancelou
    if text == "/cancelar":
        # Limpa contexto
        for key in ['adicionando_global_button', 'editando_global_button', 
                   'global_button_canal_id', 'global_button_etapa', 
                   'global_button_text', 'global_button_id']:
            context.user_data.pop(key, None)
        await notificar_sucesso(message, "cancelado")
        return True

    # Fluxo de ADICIONAR
    if context.user_data.get('adicionando_global_button'):
        etapa = context.user_data.get('global_button_etapa')
        canal_id = context.user_data.get('global_button_canal_id')
        
        if etapa == 'texto':
            context.user_data['global_button_text'] = text
            context.user_data['global_button_etapa'] = 'url'
            await mostrar_prompt_url_botao(message, text)
            return True
            
        elif etapa == 'url':
            url = text
            button_text = context.user_data.get('global_button_text')
            
            # Salva no banco
            current_buttons = await get_global_buttons(canal_id)
            new_buttons_list = [(b['text'], b['url']) for b in current_buttons]
            new_buttons_list.append((button_text, url))
            
            await save_global_buttons(canal_id, new_buttons_list)
            
            # Limpa contexto
            for key in ['adicionando_global_button', 'global_button_canal_id', 
                       'global_button_etapa', 'global_button_text']:
                context.user_data.pop(key, None)
            
            await notificar_sucesso(message, "adicionado")
            return True
            
    # Fluxo de EDITAR
    if context.user_data.get('editando_global_button'):
        etapa = context.user_data.get('global_button_etapa')
        button_id = context.user_data.get('global_button_id')
        canal_id = context.user_data.get('global_button_canal_id')
        
        if etapa == 'texto':
            context.user_data['global_button_text'] = text
            context.user_data['global_button_etapa'] = 'url'
            await mostrar_prompt_url_botao(message, text)
            return True
            
        elif etapa == 'url':
            url = text
            new_text = context.user_data.get('global_button_text')
            
            # Busca todos os botões do canal para atualizar apenas o correto
            current_buttons = await get_global_buttons(canal_id)
            updated_list = []
            for b in current_buttons:
                if b['id'] == button_id:
                    updated_list.append((new_text, url))
                else:
                    updated_list.append((b['text'], b['url']))
            
            await save_global_buttons(canal_id, updated_list)
            
            # Limpa contexto
            for key in ['editando_global_button', 'global_button_id', 
                       'global_button_canal_id', 'global_button_etapa', 'global_button_text']:
                context.user_data.pop(key, None)
                
            await notificar_sucesso(message, "editado")
            return True

    return False
