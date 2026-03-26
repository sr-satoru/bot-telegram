import logging
from datetime import datetime, timedelta, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from modules.utils import require_admin
from db_helpers import (
    get_media_groups_by_user, get_media_group, delete_media_group,
    create_media_group, update_media_group, add_media_to_group,
    get_templates_by_canal, get_template, get_global_buttons
)

logger = logging.getLogger(__name__)

# Timezone de Brasília
try:
    from zoneinfo import ZoneInfo
    BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")
except ImportError:
    try:
        import pytz
        BRASILIA_TZ = pytz.timezone("America/Sao_Paulo")
    except ImportError:
        BRASILIA_TZ = timezone(timedelta(hours=-3))

async def mostrar_menu_medias(query, context):
    """Mostra o menu de gerenciamento de mídias"""
    user_id = query.from_user.id
    dados = context.user_data.get('editando', {})
    canal_id = dados.get('canal_id')
    
    if not canal_id:
        await query.edit_message_text("❌ Erro: canal não encontrado.", parse_mode='HTML')
        return

    # Busca mídias do usuário para este canal
    media_groups = await get_media_groups_by_user(user_id, canal_id)
    
    mensagem = "📸 <b>Gerenciar Mídias</b>\n\n"
    mensagem += "Aqui você pode salvar fotos e vídeos para usar em suas postagens.\n\n"
    
    if media_groups:
        mensagem += f"<b>Grupos salvos ({len(media_groups)}):</b>\n"
    else:
        mensagem += "❌ Nenhuma mídia salva para este canal.\n\n"
        
    keyboard = []
    
    # Lista grupos
    for group in media_groups:
        group_id = group['id']
        nome = group['nome']
        num_medias = len(group.get('medias', []))
        
        display = f"📦 {nome} ({num_medias} mídias)"
        keyboard.append([
            InlineKeyboardButton(display, callback_data=f"ver_grupo_midia_{group_id}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("📸 Salvar Mídia Única", callback_data="salvar_midia_unica"),
        InlineKeyboardButton("📦 Salvar Grupo (Álbum)", callback_data="salvar_midia_agrupada")
    ])
    
    keyboard.append([
        InlineKeyboardButton("🪄 Auto-associar Template", callback_data="associar_template_automatico")
    ])
    
    keyboard.append([
        InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')

async def mostrar_detalhes_grupo_midia(query, context, group_id: int):
    """Mostra detalhes de um grupo de mídias"""
    group = await get_media_group(group_id)
    
    if not group:
        await query.edit_message_text("❌ Grupo de mídias não encontrado.", parse_mode='HTML')
        return
        
    nome = group['nome']
    medias = group.get('medias', [])
    template_id = group.get('template_id')
    
    mensagem = f"📦 <b>Grupo: {nome}</b>\n"
    mensagem += f"🆔 ID: {group_id}\n"
    mensagem += f"📸 Mídias: {len(medias)}\n"
    
    if template_id:
        template = await get_template(template_id)
        if template:
            preview = template['template_mensagem'][:30] + "..." if len(template['template_mensagem']) > 30 else template['template_mensagem']
            mensagem += f"📝 Template: {preview} (ID: {template_id})\n"
        else:
            mensagem += "📝 Template: ID " + str(template_id) + " (Não encontrado)\n"
    else:
        mensagem += "📝 Template: ❌ Nenhum associado\n"
        
    keyboard = [
        [
            InlineKeyboardButton("👁️ Preview", callback_data=f"preview_grupo_midia_{group_id}"),
            InlineKeyboardButton("📝 Mudar Template", callback_data=f"associar_template_grupo_{group_id}")
        ]
    ]
    
    if template_id:
        keyboard[0].append(InlineKeyboardButton("❌ Remover Template", callback_data=f"remover_template_grupo_{group_id}"))
        
    keyboard.append([
        InlineKeyboardButton("🗑️ Deletar", callback_data=f"deletar_grupo_midia_{group_id}"),
        InlineKeyboardButton("⬅️ Voltar", callback_data="edit_medias")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')

async def enviar_preview_grupo_midia(query, context, group_id: int, media_handler, db):
    """Envia preview do grupo de mídias com template e botões"""
    group = await get_media_group(group_id)
    
    if not group:
        await query.edit_message_text("❌ Grupo de mídias não encontrado.", parse_mode='HTML')
        return
        
    if not group.get('medias'):
        await query.edit_message_text("❌ Grupo de mídias está vazio.", parse_mode='HTML')
        return
    
    # Busca template se houver associado
    template = None
    if group.get('template_id'):
        template = await get_template(group['template_id'])
    
    # Busca botões globais do canal
    global_buttons = None
    if group.get('canal_id'):
        global_buttons = await get_global_buttons(group['canal_id'])
    
    # Envia mensagem de carregamento
    await query.answer("📤 Enviando preview...")
    await query.edit_message_text("📤 <b>Enviando preview...</b>", parse_mode='HTML')
    
    try:
        user_id = query.from_user.id
        success = await media_handler.send_media_group_with_template(
            context=context,
            chat_id=user_id,
            media_group=group,
            template=template,
            global_buttons=global_buttons,
            database=db,
            use_auto_template=True
        )
        
        if success:
            keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data=f"ver_grupo_midia_{group_id}")]]
            await query.edit_message_text(
                "✅ <b>Preview enviado!</b>\n\nVerifique a mensagem acima.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        else:
            await query.edit_message_text("❌ Erro ao enviar preview.")
    except Exception as e:
        logger.error(f"Erro ao enviar preview: {e}")
        await query.edit_message_text(f"❌ Erro ao enviar preview: {str(e)[:100]}")

@require_admin
async def finalizar_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando para finalizar criação de grupo de mídias"""
    if not context.user_data.get('salvando_midia') or context.user_data.get('tipo_midia') != 'agrupada':
        await update.message.reply_text("❌ Você não está criando um grupo de mídias.")
        return
    
    medias_temp = context.user_data.get('medias_temporarias', [])
    if len(medias_temp) == 0:
        await update.message.reply_text("❌ Nenhuma mídia foi adicionada.")
        return
    
    user_id = update.message.from_user.id
    canal_id = context.user_data.get('canal_id_midia')
    
    group_id = await create_media_group(
        nome=f"Grupo {datetime.now(BRASILIA_TZ).strftime('%d/%m/%Y %H:%M')}",
        user_id=user_id,
        canal_id=canal_id
    )
    
    for ordem, media_id in enumerate(medias_temp, start=1):
        await add_media_to_group(group_id, media_id, ordem=ordem)
    
    # Limpa contexto
    for key in ['salvando_midia', 'tipo_midia', 'canal_id_midia', 'medias_temporarias']:
        context.user_data.pop(key, None)
    
    keyboard = [[InlineKeyboardButton("⬅️ Voltar ao Canal", callback_data=f"editar_canal_{canal_id}")]]
    await update.message.reply_text(
        f"✅ <b>Grupo criado!</b>\n\nID: {group_id}\nMídias: {len(medias_temp)}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_edit_media_callback(query, context, media_handler, db):
    """Handlers de callback para mídias"""
    data = query.data
    
    if data == "edit_medias":
        await mostrar_menu_medias(query, context)
        return True
        
    elif data == "salvar_midia_unica":
        canal_id = context.user_data.get('editando', {}).get('canal_id')
        context.user_data.update({'salvando_midia': True, 'tipo_midia': 'unica', 'canal_id_midia': canal_id})
        await query.edit_message_text("📸 <b>Mídia Única</b>\n\nEnvie uma foto ou vídeo.", 
                                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="edit_medias")]]), 
                                    parse_mode='HTML')
        return True
        
    elif data == "salvar_midia_agrupada":
        canal_id = context.user_data.get('editando', {}).get('canal_id')
        context.user_data.update({'salvando_midia': True, 'tipo_midia': 'agrupada', 'canal_id_midia': canal_id, 'medias_temporarias': []})
        await query.edit_message_text("📦 <b>Mídia Agrupada</b>\n\nEnvie até 10 mídias e use /finalizar_grupo.", 
                                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="edit_medias")]]), 
                                    parse_mode='HTML')
        return True
        
    elif data.startswith("ver_grupo_midia_"):
        await mostrar_detalhes_grupo_midia(query, context, int(data.split("_")[-1]))
        return True
        
    elif data.startswith("deletar_grupo_midia_"):
        group_id = int(data.split("_")[-1])
        keyboard = [[InlineKeyboardButton("✅ Sim", callback_data=f"confirmar_deletar_grupo_{group_id}"),
                     InlineKeyboardButton("❌ Não", callback_data="edit_medias")]]
        await query.edit_message_text("⚠️ Deletar este grupo?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return True
        
    elif data.startswith("confirmar_deletar_grupo_"):
        if await delete_media_group(int(data.split("_")[-1])):
            await query.answer("✅ Deletado!")
            await mostrar_menu_medias(query, context)
        return True
        
    elif data.startswith("preview_grupo_midia_"):
        await enviar_preview_grupo_midia(query, context, int(data.split("_")[-1]), media_handler, db)
        return True

    elif data.startswith("associar_template_grupo_"):
        group_id = int(data.split("_")[-1])
        canal_id = context.user_data.get('editando', {}).get('canal_id')
        templates = await get_templates_by_canal(canal_id)
        if not templates:
            await query.answer("❌ Nenhum template encontrado.", show_alert=True)
            return True
        keyboard = []
        for t in templates:
            preview = t['template_mensagem'][:30] + "..."
            keyboard.append([InlineKeyboardButton(f"📄 {preview}", callback_data=f"conf_assoc_temp_{group_id}_{t['id']}")])
        keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data=f"ver_grupo_midia_{group_id}")])
        await query.edit_message_text("📝 Escolha o template:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return True

    elif data.startswith("conf_assoc_temp_"):
        parts = data.split("_")
        group_id, template_id = int(parts[-2]), int(parts[-1])
        await update_media_group(group_id, template_id=template_id)
        await query.answer("✅ Template associado!")
        await mostrar_detalhes_grupo_midia(query, context, group_id)
        return True

    elif data.startswith("remover_template_grupo_"):
        group_id = int(data.split("_")[-1])
        await update_media_group(group_id, remove_template=True)
        await query.answer("✅ Template removido!")
        await mostrar_detalhes_grupo_midia(query, context, group_id)
        return True

    elif data == "associar_template_automatico":
        canal_id = context.user_data.get('editando', {}).get('canal_id')
        templates = await get_templates_by_canal(canal_id)
        if len(templates) == 1:
            template_id = templates[0]['id']
            media_groups = await get_media_groups_by_user(query.from_user.id, canal_id)
            count = 0
            for g in media_groups:
                if not g.get('template_id'):
                    await update_media_group(g['id'], template_id=template_id)
                    count += 1
            await query.answer(f"✅ {count} grupos atualizados!")
            await mostrar_menu_medias(query, context)
        else:
            await query.answer("❌ Use associação manual (múltiplos templates encontrados).", show_alert=True)
        return True

    return False

async def handle_edit_media_input(update: Update, context: ContextTypes.DEFAULT_TYPE, media_handler):
    """Processa entrada de mídias (fotos/vídeos)"""
    if not context.user_data.get('salvando_midia'):
        return False
        
    tipo = context.user_data.get('tipo_midia')
    canal_id = context.user_data.get('canal_id_midia')
    media_id = await media_handler.save_media_from_message(update)
    
    if not media_id:
        await update.message.reply_text("❌ Erro ao salvar mídia.")
        return True
        
    if tipo == 'unica':
        group_id = await create_media_group(
            nome=f"Mídia Única - {datetime.now(BRASILIA_TZ).strftime('%d/%m/%Y %H:%M')}",
            user_id=update.message.from_user.id,
            canal_id=canal_id
        )
        await add_media_to_group(group_id, media_id, ordem=1)
        await update.message.reply_text(f"✅ Mídia salva! ID: {group_id}")
    else:
        medias = context.user_data.get('medias_temporarias', [])
        if len(medias) >= 10:
            await update.message.reply_text("❌ Limite de 10 mídias.")
        else:
            medias.append(media_id)
            context.user_data['medias_temporarias'] = medias
            await update.message.reply_text(f"✅ Adicionada ({len(medias)}/10). Use /finalizar_grupo para salvar.")
            
    return True
