"""
Helpers async do Prisma para uso em bot-main.py.

Substitui completamente a classe Database de database.py.
Todas as funções são async e usam o cliente Prisma de db.py.

Uso:
    from db_helpers import (
        is_admin_db, save_canal, get_canal, get_all_canais, ...
    )
"""

from typing import Optional, List, Tuple, Dict
from db import prisma


# ──────────────────────────────────────────────
# ADMINS
# ──────────────────────────────────────────────

async def is_admin_db(user_id: int) -> bool:
    result = await prisma.admin.find_unique(where={"user_id": user_id})
    return result is not None

async def add_admin(user_id: int, username: Optional[str] = None) -> bool:
    try:
        await prisma.admin.create(data={"user_id": user_id, "username": username})
        return True
    except Exception:
        return False  # Já existe

async def remove_admin(user_id: int) -> bool:
    result = await prisma.admin.delete_many(where={"user_id": user_id})
    return result > 0

async def get_all_admins() -> List[Dict]:
    admins = await prisma.admin.find_many(order={"created_at": "desc"})
    return [{"user_id": a.user_id, "username": a.username, "created_at": a.created_at} for a in admins]

async def get_admin(user_id: int) -> Optional[Dict]:
    a = await prisma.admin.find_unique(where={"user_id": user_id})
    if not a:
        return None
    return {"user_id": a.user_id, "username": a.username, "created_at": a.created_at}


# ──────────────────────────────────────────────
# CANAIS
# ──────────────────────────────────────────────

async def save_canal(nome: str, ids_canal: List[str], horarios: List[str], user_id: int) -> int:
    canal = await prisma.canal.create(
        data={
            "nome": nome,
            "user_id": user_id,
            "ids": {
                "create": [{"telegram_id": str(tid), "ordem": i + 1} for i, tid in enumerate(ids_canal)]
            },
            "horarios": {
                "create": [{"horario": h, "ordem": i + 1} for i, h in enumerate(horarios)]
            },
        }
    )
    return canal.id

async def get_canal(canal_id: int) -> Optional[Dict]:
    c = await prisma.canal.find_unique(
        where={"id": canal_id},
        include={
            "ids": {"order_by": {"ordem": "asc"}},
            "horarios": {"order_by": {"ordem": "asc"}}
        }
    )
    if not c:
        return None
    return {
        "id": c.id, "nome": c.nome, "user_id": c.user_id,
        "ids": [ci.telegram_id for ci in c.ids],
        "horarios": [h.horario for h in c.horarios],
        "created_at": c.created_at,
    }

async def get_all_canais(user_id: Optional[int] = None) -> List[Dict]:
    where = {"user_id": user_id} if user_id else {}
    canais = await prisma.canal.find_many(
        where=where,
        include={
            "ids": {"order_by": {"ordem": "asc"}},
            "horarios": {"order_by": {"ordem": "asc"}}
        },
        order={"created_at": "desc"}
    )
    return [
        {
            "id": c.id, "nome": c.nome, "user_id": c.user_id,
            "ids": [ci.telegram_id for ci in c.ids],
            "horarios": [h.horario for h in c.horarios],
            "created_at": c.created_at,
        }
        for c in canais
    ]

async def delete_canal(canal_id: int) -> bool:
    result = await prisma.canal.delete_many(where={"id": canal_id})
    return result > 0

async def update_canal(canal_id: int, nome: Optional[str] = None,
                       ids_canal: Optional[List[str]] = None,
                       horarios: Optional[List[str]] = None) -> bool:
    if nome:
        await prisma.canal.update(where={"id": canal_id}, data={"nome": nome})

    if ids_canal is not None:
        await prisma.canalid.delete_many(where={"canal_id": canal_id})
        for i, tid in enumerate(ids_canal):
            await prisma.canalid.create(data={"canal_id": canal_id, "telegram_id": str(tid), "ordem": i + 1})

    if horarios is not None:
        await prisma.horario.delete_many(where={"canal_id": canal_id})
        for i, h in enumerate(horarios):
            await prisma.horario.create(data={"canal_id": canal_id, "horario": h, "ordem": i + 1})

    return True


# ──────────────────────────────────────────────
# TEMPLATES
# ──────────────────────────────────────────────

async def save_template(canal_id: int, template_mensagem: str, links: List[Tuple[str, str]]) -> int:
    template = await prisma.template.create(
        data={
            "canal_id": canal_id,
            "template_mensagem": template_mensagem,
            "links": {
                "create": [
                    {"segmento_com_link": seg, "link_da_mensagem": url, "ordem": i + 1}
                    for i, (seg, url) in enumerate(links)
                ]
            }
        }
    )
    return template.id

async def get_template(template_id: int) -> Optional[Dict]:
    t = await prisma.template.find_unique(
        where={"id": template_id},
        include={
            "links": {"order_by": {"ordem": "asc"}},
            "inline_buttons": {"order_by": {"ordem": "asc"}}
        }
    )
    if not t:
        return None
    return {
        "id": t.id, "canal_id": t.canal_id,
        "template_mensagem": t.template_mensagem,
        "created_at": t.created_at,
        "links": [{"id": l.id, "segmento": l.segmento_com_link, "link": l.link_da_mensagem, "ordem": l.ordem} for l in t.links],
        "inline_buttons": [{"id": b.id, "text": b.button_text, "url": b.button_url, "ordem": b.ordem, "status": b.status} for b in t.inline_buttons],
    }

async def get_templates_by_canal(canal_id: int) -> List[Dict]:
    templates = await prisma.template.find_many(
        where={"canal_id": canal_id},
        include={
            "links": {"order_by": {"ordem": "asc"}},
            "inline_buttons": {"order_by": {"ordem": "asc"}}
        },
        order={"created_at": "desc"}
    )
    return [
        {
            "id": t.id, "canal_id": t.canal_id,
            "template_mensagem": t.template_mensagem,
            "created_at": t.created_at,
            "links": [{"segmento": l.segmento_com_link, "link": l.link_da_mensagem, "ordem": l.ordem} for l in t.links],
            "inline_buttons": [{"id": b.id, "text": b.button_text, "url": b.button_url, "ordem": b.ordem, "status": b.status} for b in t.inline_buttons],
        }
        for t in templates
    ]

async def delete_template(template_id: int) -> bool:
    result = await prisma.template.delete_many(where={"id": template_id})
    return result > 0

async def get_template_with_link_ids(template_id: int) -> Optional[Dict]:
    """Retorna template com links como tupla (link_id, segmento, url, ordem) para edição"""
    t = await prisma.template.find_unique(
        where={"id": template_id},
        include={
            "links": {"order_by": {"ordem": "asc"}},
            "inline_buttons": {"order_by": {"ordem": "asc"}}
        }
    )
    if not t:
        return None
    return {
        "id": t.id, "canal_id": t.canal_id,
        "template_mensagem": t.template_mensagem,
        "links": [(l.id, l.segmento_com_link, l.link_da_mensagem, l.ordem) for l in t.links],
        "inline_buttons": [{"id": b.id, "text": b.button_text, "url": b.button_url, "ordem": b.ordem, "status": b.status} for b in t.inline_buttons],
    }

async def update_link(link_id: int, link_url: str) -> bool:
    result = await prisma.templatelink.update_many(
        where={"id": link_id}, data={"link_da_mensagem": link_url}
    )
    return result > 0

async def update_all_links(template_id: int, link_url: str) -> int:
    return await prisma.templatelink.update_many(
        where={"template_id": template_id}, data={"link_da_mensagem": link_url}
    )

async def get_link_info(link_id: int) -> Optional[Tuple]:
    """Retorna (id, template_id, segmento, url, ordem) ou None"""
    l = await prisma.templatelink.find_unique(where={"id": link_id})
    if not l:
        return None
    return (l.id, l.template_id, l.segmento_com_link, l.link_da_mensagem, l.ordem)


# ──────────────────────────────────────────────
# BOTÕES INLINE DO TEMPLATE
# ──────────────────────────────────────────────

async def save_inline_buttons(template_id: int, buttons: List[Tuple[str, str]]) -> bool:
    await prisma.templateinlinebutton.delete_many(where={"template_id": template_id})
    for i, (text, url) in enumerate(buttons):
        await prisma.templateinlinebutton.create(
            data={"template_id": template_id, "button_text": text, "button_url": url, "ordem": i + 1}
        )
    return True

async def get_inline_buttons(template_id: int) -> List[Dict]:
    buttons = await prisma.templateinlinebutton.find_many(
        where={"template_id": template_id}, order={"ordem": "asc"}
    )
    return [{"id": b.id, "text": b.button_text, "url": b.button_url, "ordem": b.ordem, "status": b.status} for b in buttons]

async def delete_inline_button(button_id: int) -> bool:
    result = await prisma.templateinlinebutton.delete_many(where={"id": button_id})
    return result > 0

async def get_inline_button_info(button_id: int) -> Optional[Dict]:
    b = await prisma.templateinlinebutton.find_unique(where={"id": button_id})
    if not b:
        return None
    return {"id": b.id, "template_id": b.template_id, "text": b.button_text, "url": b.button_url, "ordem": b.ordem, "status": b.status}

async def update_inline_button(button_id: int, data: Dict) -> bool:
    """Atualiza campos de um botão inline (text, url)"""
    update_data = {}
    if "text" in data: update_data["button_text"] = data["text"]
    if "url" in data: update_data["button_url"] = data["url"]
    
    result = await prisma.templateinlinebutton.update_many(
        where={"id": button_id},
        data=update_data
    )
    return result > 0

async def toggle_inline_button_status(button_id: int) -> Optional[str]:
    """Alterna o status entre ATIVO e INATIVO. Retorna novo status."""
    b = await prisma.templateinlinebutton.find_unique(where={"id": button_id})
    if not b: return None
    
    new_status = "INATIVO" if b.status == "ATIVO" else "ATIVO"
    await prisma.templateinlinebutton.update(
        where={"id": button_id},
        data={"status": new_status}
    )
    return new_status


# ──────────────────────────────────────────────
# BOTÕES GLOBAIS DO CANAL
# ──────────────────────────────────────────────

async def get_global_buttons(canal_id: int) -> List[Dict]:
    buttons = await prisma.canalglobalbutton.find_many(
        where={"canal_id": canal_id}, order={"ordem": "asc"}
    )
    return [{"id": b.id, "text": b.button_text, "url": b.button_url, "ordem": b.ordem} for b in buttons]

async def save_global_buttons(canal_id: int, buttons: List[Tuple[str, str]]) -> bool:
    await prisma.canalglobalbutton.delete_many(where={"canal_id": canal_id})
    for i, (text, url) in enumerate(buttons):
        await prisma.canalglobalbutton.create(
            data={"canal_id": canal_id, "button_text": text, "button_url": url, "ordem": i + 1}
        )
    return True

async def delete_global_button(button_id: int) -> bool:
    result = await prisma.canalglobalbutton.delete_many(where={"id": button_id})
    return result > 0

async def get_global_button_info(button_id: int) -> Optional[Dict]:
    b = await prisma.canalglobalbutton.find_unique(where={"id": button_id})
    if not b:
        return None
    return {"id": b.id, "canal_id": b.canal_id, "text": b.button_text, "url": b.button_url, "ordem": b.ordem}

async def update_global_button(button_id: int, data: Dict) -> bool:
    """Atualiza campos de um botão global (text, url)"""
    update_data = {}
    if "text" in data: update_data["button_text"] = data["text"]
    if "url" in data: update_data["button_url"] = data["url"]
    
    result = await prisma.canalglobalbutton.update_many(
        where={"id": button_id},
        data=update_data
    )
    return result > 0


# ──────────────────────────────────────────────
# MÍDIAS E GRUPOS DE MÍDIAS
# ──────────────────────────────────────────────

async def save_media(file_id: str, file_unique_id: str, media_type: str,
                     file_size: Optional[int] = None, width: Optional[int] = None,
                     height: Optional[int] = None, duration: Optional[int] = None,
                     thumbnail_file_id: Optional[str] = None) -> int:
    media = await prisma.media.create(data={
        "file_id": file_id, "file_unique_id": file_unique_id,
        "media_type": media_type, "file_size": file_size,
        "width": width, "height": height, "duration": duration,
        "thumbnail_file_id": thumbnail_file_id,
    })
    return media.id

async def create_media_group(nome: str, user_id: int,
                             canal_id: Optional[int] = None,
                             template_id: Optional[int] = None) -> int:
    group = await prisma.mediagroup.create(data={
        "nome": nome, "user_id": user_id,
        "canal_id": canal_id, "template_id": template_id,
    })
    return group.id

async def add_media_to_group(media_group_id: int, media_id: int, ordem: int,
                             caption: Optional[str] = None) -> bool:
    await prisma.mediagroupitem.create(data={
        "media_group_id": media_group_id, "media_id": media_id,
        "ordem": ordem, "caption": caption,
    })
    return True

async def get_media_group(group_id: int) -> Optional[Dict]:
    g = await prisma.mediagroup.find_unique(
        where={"id": group_id},
        include={"items": {"include": {"media": True}, "order_by": {"ordem": "asc"}}}
    )
    if not g:
        return None
    medias = []
    for item in g.items:
        m = item.media
        medias.append({
            "id": m.id, "file_id": m.file_id, "file_unique_id": m.file_unique_id,
            "media_type": m.media_type, "file_size": m.file_size,
            "width": m.width, "height": m.height, "duration": m.duration,
            "thumbnail_file_id": m.thumbnail_file_id,
            "ordem": item.ordem, "caption": item.caption,
        })
    return {
        "id": g.id, "nome": g.nome, "user_id": g.user_id,
        "canal_id": g.canal_id, "template_id": g.template_id,
        "created_at": g.created_at, "medias": medias,
    }

async def get_media_groups_by_user(user_id: int, canal_id: Optional[int] = None) -> List[Dict]:
    where: Dict = {"user_id": user_id}
    if canal_id:
        where["canal_id"] = canal_id
    groups = await prisma.mediagroup.find_many(
        where=where,
        include={"items": True},
        order={"created_at": "desc"}
    )
    return [
        {
            "id": g.id, "nome": g.nome, "user_id": g.user_id,
            "canal_id": g.canal_id, "template_id": g.template_id,
            "media_count": len(g.items), "created_at": g.created_at,
        }
        for g in groups
    ]

async def delete_media_group(group_id: int) -> bool:
    result = await prisma.mediagroup.delete_many(where={"id": group_id})
    return result > 0

async def update_media_group(group_id: int, nome: Optional[str] = None,
                             canal_id: Optional[int] = None,
                             template_id: Optional[int] = None,
                             remove_template: bool = False) -> bool:
    data: Dict = {}
    if nome is not None:
        data["nome"] = nome
    if canal_id is not None:
        data["canal_id"] = canal_id
    if remove_template:
        data["template_id"] = None
    elif template_id is not None:
        data["template_id"] = template_id

    if not data:
        return False

    await prisma.mediagroup.update(where={"id": group_id}, data=data)
    return True
