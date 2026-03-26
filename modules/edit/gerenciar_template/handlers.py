import logging
from telegram import Update
from telegram.ext import ContextTypes
from db_helpers import (
    get_template_with_link_ids, update_link, update_all_links, 
    get_link_info, save_template, save_inline_buttons, 
    get_inline_buttons, delete_inline_button, get_inline_button_info, 
    get_global_buttons, update_media_group, get_canal,
    delete_template, get_templates_by_canal, get_template
)
from modules.utils import strip_html_tags
from .ui import (
    mostrar_lista_templates, mostrar_preview_template, 
    mostrar_painel_edicao_links, mostrar_confirmacao_delecao,
    mostrar_menu_tipo_link_geral, mostrar_prompt_criacao_template,
    mostrar_escolha_link_template, mostrar_prompt_link_estatico,
    mostrar_prompt_edicao_global, mostrar_prompt_mudar_link_canal,
    mostrar_erro_template
)
from modules.buton_global.handlers import (
    handle_global_button_callback, handle_global_button_message,
    handle_template_button_callback, handle_any_button_message
)

logger = logging.getLogger(__name__)

# A função show_edit_panel foi movida para ui.py

async def handle_edit_template_callback(query, context, parser):
    """Handlers de callback para gerenciamento de templates"""
    data = query.data
    user_id = query.from_user.id
    
    if data == "edit_templates":
        # Lista templates do canal
        dados = context.user_data.get('editando', {})
        canal_id = dados.get('canal_id')
        
        if not canal_id:
            await mostrar_erro_template(query, "Erro: canal não encontrado.")
            return True
        
        templates = await get_templates_by_canal(canal_id)
        await mostrar_lista_templates(query, templates, canal_id, context)
        return True

    elif data.startswith("preview_template_"):
        # Mostra preview do template formatado
        template_id = int(data.split("_")[-1])
        template = await get_template(template_id)
        
        if not template:
            await mostrar_erro_template(query)
            return True
        
        template_mensagem = template['template_mensagem']
        links = template['links']
        inline_buttons = template.get('inline_buttons', [])
        canal_id = template.get('canal_id')
        
        global_buttons = []
        if canal_id:
            global_buttons = await get_global_buttons(canal_id)
        
        await mostrar_preview_template(query, template, global_buttons, parser, context)
        return True
    elif data.startswith("adicionar_template_"):
        # Inicia criação de novo template para o canal
        canal_id = int(data.split("_")[-1])
        context.user_data['criando_template'] = True
        context.user_data['canal_id_template'] = canal_id
        context.user_data['etapa'] = 'template_mensagem'
        
        # Garante que 'editando' tenha o canal_id para o retorno ao menu
        if 'editando' not in context.user_data:
            canal = await get_canal(canal_id)
            context.user_data['editando'] = {
                'canal_id': canal_id, 'nome': canal['nome'], 
                'ids': canal['ids'].copy(), 'horarios': canal['horarios'].copy()
            }
        
        await mostrar_prompt_criacao_template(query)
        return True

    elif data.startswith("deletar_template_"):
        # Confirmação para deletar template
        template_id = int(data.split("_")[-1])
        template = await get_template(template_id)
        
        if not template:
            await mostrar_erro_template(query)
            return True
        
        template_msg = template['template_mensagem']
        # Strip tags before slicing to avoid unclosed HTML tags
        clean_text = strip_html_tags(template_msg)
        preview = clean_text[:40] + "..." if len(clean_text) > 40 else clean_text
        await mostrar_confirmacao_delecao(query, template_id, preview)
        return True

    elif data.startswith("confirmar_deletar_template_"):
        template_id = int(data.split("_")[-1])
        
        # Busca canal_id ANTES de deletar para poder voltar à lista
        canal_id = context.user_data.get('editando', {}).get('canal_id')
        if not canal_id:
            t = await get_template(template_id)
            canal_id = t['canal_id'] if t else None
            
        deleted = await delete_template(template_id)
        if deleted:
            await query.answer("✅ Template deletado!", show_alert=True)
            if canal_id:
                templates = await get_templates_by_canal(canal_id)
                await mostrar_lista_templates(query, templates, canal_id, context)
            else:
                await query.edit_message_text("✅ Template deletado. Volte ao menu principal.")
        else:
            await mostrar_erro_template(query, "Erro ao deletar template.")
        return True

    elif data.startswith("edit_template_"):
        template_id = int(data.split("_")[-1])
        context.user_data['editing_template_id'] = template_id
        template = await get_template_with_link_ids(template_id)
        if not template: return True
        inline_buttons = await get_inline_buttons(template_id)
        await mostrar_painel_edicao_links(query, template, inline_buttons, context)
        return True

    elif data.startswith("edit_link_"):
        link_id = int(data.split("_")[-1])
        link_info = await get_link_info(link_id)
        if not link_info: return True
        
        lid, tid, segmento, url, ordem = link_info
        context.user_data['editing_link_id'] = lid
        context.user_data['editing_template_id'] = tid
        context.user_data['editing_segmento'] = segmento
        context.user_data['editing_ordem'] = ordem
        
        await query.edit_message_text(
            f"🔗 <b>Editando Link {ordem}</b>\n\n"
            f"Segmento: <code>{segmento}</code>\n"
            f"Link atual: <code>{url}</code>\n\n"
            "Envie o novo link para este segmento ou use /cancelar para voltar:",
            parse_mode='HTML'
        )
        return True

    elif data.startswith("mudar_link_geral_canal_"):
        canal_id = int(data.split("_")[-1])
        templates = await get_templates_by_canal(canal_id)
        num_templates = len(templates)
        await mostrar_menu_tipo_link_geral(query, canal_id, num_templates)
        return True

    elif data.startswith(("mudar_link_global_canal_", "mudar_link_bot_canal_", "mudar_link_externo_canal_")):
        canal_id = int(data.split("_")[-1])
        context.user_data['mudando_link_canal_id'] = canal_id
        if "global" in data:
            context.user_data['mudando_link_global_canal'] = True
            await mostrar_prompt_mudar_link_canal(query, 'global')
        elif "bot" in data:
            context.user_data['mudando_link_bot_canal'] = True
            await mostrar_prompt_mudar_link_canal(query, 'bot')
        else:
            context.user_data['mudando_link_externo_canal'] = True
            await mostrar_prompt_mudar_link_canal(query, 'externo')
        return True

    elif data.startswith("edit_all_"):
        template_id = int(data.split("_")[-1])
        template = await get_template_with_link_ids(template_id)
        if not template: return True
        context.user_data['editing_all_links'] = True
        context.user_data['editing_template_id'] = template_id
        context.user_data['editing_num_links'] = len(template['links'])
        await mostrar_prompt_edicao_global(query, len(template['links']))
        return True

    elif data == "confirmar_salvar_estatico":
        parsed = context.user_data.get('pending_template')
        canal_id = context.user_data.get('canal_id_template')
        if not parsed or not canal_id: return True
        tid = await save_template(canal_id, parsed['template_mensagem'], [])
        for key in ['criando_template', 'etapa', 'pending_template', 'canal_id_template']: context.user_data.pop(key, None)
        await query.answer("✅ Template estático salvo!", show_alert=True)
        templates = await get_templates_by_canal(canal_id)
        await mostrar_lista_templates(query, templates, canal_id, context)
        return True

    elif data == "link_choice_keep":
        parsed = context.user_data.get('pending_template')
        canal_id = context.user_data.get('canal_id_template')
        if not parsed or not canal_id: return True
        # Usa links originais capturados
        links = [(seg, url) for seg, url in zip(parsed['segmentos'], parsed['urls_originais'])]
        tid = await save_template(canal_id, parsed['template_mensagem'], links)
        for key in ['criando_template', 'etapa', 'pending_template', 'canal_id_template']: context.user_data.pop(key, None)
        await query.answer("✅ Template salvo com links originais!", show_alert=True)
        templates = await get_templates_by_canal(canal_id)
        await mostrar_lista_templates(query, templates, canal_id, context)
        return True

    elif data == "link_choice_same":
        context.user_data['use_same_link'] = True
        context.user_data['etapa'] = 'recebendo_link'
        await query.edit_message_text("🔗 Envie o link único que será usado em todos os segmentos:", parse_mode='HTML')
        return True

    elif data == "link_choice_separate":
        context.user_data['use_same_link'] = False
        context.user_data['etapa'] = 'recebendo_link'
        context.user_data['current_link_index'] = 0
        context.user_data['links_received'] = []
        parsed = context.user_data.get('pending_template')
        await query.edit_message_text(f"🔗 Envie o link para '{parsed['segmentos'][0]}':", parse_mode='HTML')
        return True

    # Botões Inline (Template) delegados para modules.buton_global
    if await handle_template_button_callback(query, context):
        return True

    # Botões Globais delegados para modules.buton_global
    if await handle_global_button_callback(query, context):
        return True

    return False

async def handle_edit_template_message(update: Update, context: ContextTypes.DEFAULT_TYPE, parser):
    """Processa mensagens relacionadas a templates"""
    user_data = context.user_data
    message_text = update.message.text or update.message.caption or ""
    message_html = update.message.text_html or update.message.caption_html or message_text

    # Comando cancelar
    if message_text == "/cancelar":
        # Se estiver editando links de um template
        if 'editing_link_id' in user_data or 'editing_all_links' in user_data:
            tid = user_data.get('editing_template_id')
            for key in ['editing_link_id', 'editing_all_links', 'editing_num_links', 'editing_segmento', 'editing_ordem']: 
                user_data.pop(key, None)
            if tid:
                template = await get_template_with_link_ids(tid)
                inline_buttons = await get_inline_buttons(tid)
                await mostrar_painel_edicao_links(update.message, template, inline_buttons, context, success_message="❌ Operação cancelada.")
                return True

    # Fluxo de Criação
    if user_data.get('criando_template'):
        etapa = user_data.get('etapa')
        canal_id = user_data.get('canal_id_template')
        
        if etapa == 'template_mensagem':
            parsed = parser.parse_and_save_template(message_html)
            user_data['pending_template'] = parsed
            user_data['original_message'] = message_html
            
            if parsed['num_links'] == 0:
                await mostrar_prompt_link_estatico(update.message)
            else:
                await mostrar_escolha_link_template(update.message, parsed['num_links'])
            return True
            
        elif etapa == 'recebendo_link':
            # Validação básica
            if not message_text.startswith(('http', 'https')):
                await update.message.reply_text("❌ Envie um link válido.")
                return True
                
            parsed = user_data['pending_template']
            if user_data.get('use_same_link'):
                links = [(seg, message_text.strip()) for seg in parsed['segmentos']]
                tid = await save_template(canal_id, parsed['template_mensagem'], links)
                for key in ['criando_template', 'etapa', 'pending_template', 'use_same_link']: user_data.pop(key, None)
                templates = await get_templates_by_canal(canal_id)
                await mostrar_lista_templates(update.message, templates, canal_id, context, extra_text=f"✅ Template salvo! ID: {tid}")
            else:
                idx = user_data.get('current_link_index', 0)
                user_data['links_received'].append((parsed['segmentos'][idx], message_text.strip()))
                idx += 1
                user_data['current_link_index'] = idx
                
                if idx < len(parsed['segmentos']):
                    await update.message.reply_text(f"🔗 Envie o link para '{parsed['segmentos'][idx]}':")
                else:
                    tid = await save_template(canal_id, parsed['template_mensagem'], user_data['links_received'])
                    for key in ['criando_template', 'etapa', 'pending_template', 'links_received', 'current_link_index']: user_data.pop(key, None)
                    templates = await get_templates_by_canal(canal_id)
                    await mostrar_lista_templates(update.message, templates, canal_id, context, extra_text=f"✅ Todos os links recebidos! ID: {tid}")
            return True

    # Fluxo de Edição
    # Fluxos de botão agora são delegados completamente para handle_any_button_message

    if 'editing_all_links' in user_data:
        tid = user_data['editing_template_id']
        await update_all_links(tid, message_text.strip())
        
        # Recupera dados para mostrar o painel editado
        template = await get_template_with_link_ids(tid)
        inline_buttons = await get_inline_buttons(tid)
        
        for key in ['editing_all_links', 'editing_num_links']: user_data.pop(key, None)
        
        await update.message.reply_text("✅ Todos os links atualizados!")
        await mostrar_painel_edicao_links(update.message, template, inline_buttons, context)
        return True

    if 'editing_link_id' in user_data:
        lid = user_data['editing_link_id']
        tid = user_data['editing_template_id']
        await update_link(lid, message_text.strip())
        
        # Recupera dados para mostrar o painel editado
        template = await get_template_with_link_ids(tid)
        inline_buttons = await get_inline_buttons(tid)
        
        # Limpa contexto de edição de link MAS mantém editing_template_id se necessário para o painel?
        # mostrar_painel_edicao_links já recebe o template objeto.
        for key in ['editing_link_id', 'editing_segmento', 'editing_ordem']: user_data.pop(key, None)
        
        await update.message.reply_text("✅ Link atualizado!")
        await mostrar_painel_edicao_links(update.message, template, inline_buttons, context)
        return True

    # Fluxo de Mudar Link Global Canal
    if 'mudando_link_global_canal' in user_data:
        cid = user_data['mudando_link_canal_id']
        templates = await get_templates_by_canal(cid)
        for t in templates: await update_all_links(t['id'], message_text.strip())
        user_data.pop('mudando_link_global_canal', None)
        user_data.pop('mudando_link_canal_id', None)
        templates = await get_templates_by_canal(cid)
        await mostrar_lista_templates(update.message, templates, cid, context, extra_text="✅ Todos os links atualizados!")
        return True

    if 'mudando_link_bot_canal' in user_data:
        cid = user_data['mudando_link_canal_id']
        new_bot_url = message_text.strip()
        if 't.me/' not in new_bot_url:
             await update.message.reply_text("❌ Link deve ser do Telegram.")
             return True
        new_bot = new_bot_url.split('t.me/')[-1].split('?')[0]
        templates = await get_templates_by_canal(cid)
        for t in templates:
            t_data = await get_template_with_link_ids(t['id'])
            for lid, seg, url_orig, ord in t_data['links']:
                if 't.me/' in url_orig:
                    parts = url_orig.split('?')
                    new_url = f"https://t.me/{new_bot}" + (f"?{parts[1]}" if len(parts) > 1 else "")
                    await update_link(lid, new_url)
        user_data.pop('mudando_link_bot_canal', None)
        user_data.pop('mudando_link_canal_id', None)
        templates = await get_templates_by_canal(cid)
        await mostrar_lista_templates(update.message, templates, cid, context, extra_text="✅ Links de bot atualizados!")
        return True

    if 'mudando_link_externo_canal' in user_data:
        cid = user_data['mudando_link_canal_id']
        new_url = message_text.strip()
        templates = await get_templates_by_canal(cid)
        for t in templates:
            t_data = await get_template_with_link_ids(t['id'])
            for lid, seg, url_orig, ord in t_data['links']:
                if 't.me/' not in url_orig:
                    await update_link(lid, new_url)
        user_data.pop('mudando_link_externo_canal', None)
        user_data.pop('mudando_link_canal_id', None)
        templates = await get_templates_by_canal(cid)
        await mostrar_lista_templates(update.message, templates, cid, context, extra_text="✅ Links externos atualizados!")
        return True

    # Botões Inline (Template e Globais) delegados ao módulo modules.buton_global
    if await handle_any_button_message(update, context):
        return True

    return False
