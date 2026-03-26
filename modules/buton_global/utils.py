from db_helpers import (
    get_global_buttons, save_global_buttons, delete_global_button, get_global_button_info, update_global_button,
    get_inline_buttons, save_inline_buttons, delete_inline_button, get_inline_button_info, update_inline_button
)

async def get_any_buttons(parent_id: int, owner_type: str = 'canal'):
    """Retorna lista de botões dependendo do tipo (canal ou template)"""
    if owner_type == 'canal':
        return await get_global_buttons(parent_id)
    else:
        return await get_inline_buttons(parent_id)

async def save_any_buttons(parent_id: int, buttons_list: list, owner_type: str = 'canal'):
    """Salva lista de botões dependendo do tipo"""
    if owner_type == 'canal':
        return await save_global_buttons(parent_id, buttons_list)
    else:
        return await save_inline_buttons(parent_id, buttons_list)

async def delete_any_button(button_id: int, owner_type: str = 'canal'):
    """Deleta botão dependendo do tipo"""
    if owner_type == 'canal':
        return await delete_global_button(button_id)
    else:
        return await delete_inline_button(button_id)

async def get_any_button_info(button_id: int, owner_type: str = 'canal'):
    """Retorna info do botão dependendo do tipo"""
    if owner_type == 'canal':
        return await get_global_button_info(button_id)
    else:
        info = await get_inline_button_info(button_id)
        if info:
            # Padroniza para sempre ter 'canal_id' ou 'parent_id' se necessário
            # Aqui no template usamos template_id
            info['parent_id'] = info['template_id']
        return info

async def update_any_button(button_id: int, data: dict, owner_type: str = 'canal'):
    """Atualiza botão dependendo do tipo"""
    if owner_type == 'canal':
        return await update_global_button(button_id, data)
    else:
        return await update_inline_button(button_id, data)
