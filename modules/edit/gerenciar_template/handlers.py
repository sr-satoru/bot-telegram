import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from db_helpers import (
    get_template_with_link_ids, update_link, update_all_links, 
    get_link_info, save_template, save_inline_buttons, 
    get_inline_buttons, delete_inline_button, get_inline_button_info, 
    get_global_buttons, save_global_buttons, delete_global_button,
    get_inline_button_info as get_global_button_info,
    update_media_group, get_canal
)

logger = logging.getLogger(__name__)

async def show_edit_panel(query_or_message, template_id: int, context, success_message: str = None):
    """Mostra o painel de edição de links de um template"""
    template = await get_template_with_link_ids(template_id)
    
    if not template:
        if hasattr(query_or_message, 'edit_message_text'):
            await query_or_message.edit_message_text("❌ Template não encontrado.")
        else:
            await query_or_message.reply_text("❌ Template não encontrado.")
        return

    links = template['links']
    inline_buttons = await get_inline_buttons(template_id)
    
    mensagem = f"🔧 <b>Configuração de Links - ID: {template_id}</b>\n\n"
    if success_message:
        mensagem += f"{success_message}\n\n"
        
    mensagem += "📄 <b>Texto:</b>\n"
    template_msg = template['template_mensagem']
    preview = template_msg[:100] + "..." if len(template_msg) > 100 else template_msg
    mensagem += f"<i>{preview}</i>\n\n"
    
    mensagem += f"🔗 <b>Segmentos identificados ({len(links)}):</b>\n"
    
    keyboard = []
    
    # Links dinâmicos
    for link_id, segmento, url, ordem in links:
        url_display = url if len(url) <= 30 else url[:27] + "..."
        mensagem += f"{ordem}. '{segmento}'\n   → {url_display}\n\n"
        keyboard.append([
            InlineKeyboardButton(f"✏️ Editar {ordem}", callback_data=f"edit_link_{link_id}")
        ])
    
    # Botões inline individuais
    if inline_buttons:
        mensagem += "\n🔘 <b>Botões Inline:</b>\n"
        for i, button in enumerate(inline_buttons, 1):
            url_display = button['url'] if len(button['url']) <= 30 else button['url'][:27] + "..."
            mensagem += f"{i}. '{button['text']}' → {url_display}\n"
            keyboard.append([
                InlineKeyboardButton(f"✏️ Botão {i}", callback_data=f"edit_inline_button_{button['id']}"),
                InlineKeyboardButton("🗑️", callback_data=f"deletar_inline_button_{button['id']}")
            ])
            
    keyboard.append([
        InlineKeyboardButton("➕ Adicionar Botão Inline", callback_data=f"adicionar_inline_button_{template_id}")
    ])
    
    keyboard.append([
        InlineKeyboardButton("🔄 Mudar Todos os Links", callback_data=f"edit_all_{template_id}")
    ])
    
    keyboard.append([
        InlineKeyboardButton("⬅️ Voltar", callback_data="edit_templates"),
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if hasattr(query_or_message, 'edit_message_text'):
        await query_or_message.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await query_or_message.reply_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')

async def handle_edit_template_callback(query, context, parser):
    """Handlers de callback para gerenciamento de templates"""
    data = query.data
    user_id = query.from_user.id
    
    if data == "edit_templates":
        # Lista templates do canal
        dados = context.user_data.get('editando', {})
        canal_id = dados.get('canal_id')
        
        if not canal_id:
            await query.edit_message_text("❌ Erro: canal não encontrado.", parse_mode='HTML')
            return True
        
        templates = await get_templates_by_canal(canal_id)
        
        if not templates:
            keyboard = [
                [InlineKeyboardButton("➕ Adicionar Template", callback_data=f"adicionar_template_{canal_id}")],
                [InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "📝 <b>Gerenciar Templates</b>\n\n❌ Nenhum template encontrado.",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            return True
        
        mensagem = f"📝 <b>Gerenciar Templates</b>\n\n"
        mensagem += f"Total: {len(templates)} template(s)\n\n"
        
        keyboard = []
        for template in templates:
            template_id = template['id']
            template_msg = template['template_mensagem']
            preview = template_msg[:25] + "..." if len(template_msg) > 25 else template_msg
            keyboard.append([
                InlineKeyboardButton(f"📄 {preview}", callback_data=f"edit_template_{template_id}"),
                InlineKeyboardButton("👁️ Preview", callback_data=f"preview_template_{template_id}")
            ])
            keyboard.append([
                InlineKeyboardButton("🗑️ Deletar", callback_data=f"deletar_template_{template_id}")
            ])
        
        keyboard.append([
            InlineKeyboardButton("➕ Adicionar Template", callback_data=f"adicionar_template_{canal_id}")
        ])
        
        keyboard.append([
            InlineKeyboardButton("🔗 Mudar link geral", callback_data=f"mudar_link_geral_canal_{canal_id}")
        ])
        
        keyboard.append([
            InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
        return True

    elif data.startswith("preview_template_"):
        # Mostra preview do template formatado
        template_id = int(data.split("_")[-1])
        template = await get_template(template_id)
        
        if not template:
            await query.edit_message_text("❌ Template não encontrado.", parse_mode='HTML')
            return True
        
        template_mensagem = template['template_mensagem']
        links = template['links']
        inline_buttons = template.get('inline_buttons', [])
        canal_id = template.get('canal_id')
        
        # Busca botões globais do canal
        global_buttons = []
        if canal_id:
            global_buttons = await get_global_buttons(canal_id)
        
        # Converte para formato de tuplas (segmento, link_url)
        links_tuples = [(link['segmento'], link['link']) for link in links]
        
        # Formata a mensagem com links HTML
        formatted_message = parser.format_message_with_links(template_mensagem, links_tuples)
        
        # Monta mensagem com informações
        preview_text = f"👁️ <b>Preview - Template ID: {template_id}</b>\n\n"
        preview_text += f"📄 <b>Mensagem formatada:</b>\n\n"
        preview_text += formatted_message
        
        # Cria botões inline para preview (globais + individuais)
        preview_keyboard = []
        all_buttons = []
        
        # Adiciona botões globais primeiro
        if global_buttons:
            preview_text += f"\n\n🔘 <b>Botões Globais ({len(global_buttons)}):</b>\n"
            for button in global_buttons:
                preview_text += f"• 🌐 {button['text']} → {button['url'][:30]}...\n"
                all_buttons.append(InlineKeyboardButton(button['text'], url=button['url']))
        
        # Adiciona botões individuais do template
        if inline_buttons:
            preview_text += f"\n🔘 <b>Botões do Template ({len(inline_buttons)}):</b>\n"
            for button in inline_buttons:
                preview_text += f"• {button['text']} → {button['url'][:30]}...\n"
                all_buttons.append(InlineKeyboardButton(button['text'], url=button['url']))
        
        # Organiza botões em linhas (2 por linha)
        if all_buttons:
            button_row = []
            for button in all_buttons:
                button_row.append(button)
                if len(button_row) >= 2:
                    preview_keyboard.append(button_row)
                    button_row = []
            if button_row:
                preview_keyboard.append(button_row)
        
        # Botões de navegação
        nav_buttons = [
            InlineKeyboardButton("⬅️ Voltar", callback_data="edit_templates"),
            InlineKeyboardButton("✏️ Editar", callback_data=f"edit_template_{template_id}")
        ]
        preview_keyboard.append(nav_buttons)
        
        reply_markup = InlineKeyboardMarkup(preview_keyboard)
        await query.edit_message_text(preview_text, reply_markup=reply_markup, parse_mode='HTML')
        return True

    elif data.startswith("adicionar_template_"):
        # Inicia criação de novo template para o canal
        canal_id = int(data.split("_")[-1])
        context.user_data['criando_template'] = True
        context.user_data['canal_id_template'] = canal_id
        context.user_data['etapa'] = 'template_mensagem'
        
        await query.edit_message_text(
            "📝 <b>Adicionar Template</b>\n\n"
            "Envie a mensagem usando a formatação do Telegram:\n"
            "• Use <b>negrito</b>, <i>itálico</i>, <u>sublinhado</u>, etc.\n"
            "• Use <b>Inserir Link</b> (hiperlink) no próprio texto.\n\n"
            "O bot identificará todos os links e a formatação automaticamente! ✅",
            parse_mode='HTML'
        )
        return True

    elif data.startswith("deletar_template_"):
        # Confirmação para deletar template
        template_id = int(data.split("_")[-1])
        template = await get_template(template_id)
        
        if not template:
            await query.edit_message_text("❌ Template não encontrado.", parse_mode='HTML')
            return True
        
        template_msg = template['template_mensagem']
        preview = template_msg[:40] + "..." if len(template_msg) > 40 else template_msg
        
        mensagem = f"🗑️ <b>Deletar Template?</b>\n\n"
        mensagem += f"📝 ID: {template_id}\n"
        mensagem += f"📄 {preview}\n\n"
        mensagem += "⚠️ Esta ação não pode ser desfeita!"
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data=f"confirmar_deletar_template_{template_id}"),
                InlineKeyboardButton("❌ Cancelar", callback_data="edit_templates")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
        return True

    elif data.startswith("confirmar_deletar_template_"):
        template_id = int(data.split("_")[-1])
        deleted = await delete_template(template_id)
        if deleted:
            await query.answer("✅ Template deletado!")
            # Volta para lista
            await handle_edit_template_callback(query, context, parser)
        else:
            await query.edit_message_text("❌ Erro ao deletar template.")
        return True

    elif data.startswith("edit_template_"):
        template_id = int(data.split("_")[-1])
        await show_edit_panel(query, template_id, context)
        return True

    elif data.startswith("mudar_link_geral_canal_"):
        canal_id = int(data.split("_")[-1])
        templates = await get_templates_by_canal(canal_id)
        num_templates = len(templates)
        mensagem = "🔄 <b>Mudar Link Geral do Canal</b>\n\n"
        mensagem += f"⚠️ Esta ação afetará <b>TODOS os {num_templates} template(s)</b> do canal.\n\n"
        mensagem += "Escolha como os links devem ser alterados:\n"
        keyboard = [
            [InlineKeyboardButton("🌐 Link global", callback_data=f"mudar_link_global_canal_{canal_id}")],
            [InlineKeyboardButton("🤖 Link de bot", callback_data=f"mudar_link_bot_canal_{canal_id}")],
            [InlineKeyboardButton("🔗 Link externo", callback_data=f"mudar_link_externo_canal_{canal_id}")],
            [InlineKeyboardButton("⬅️ Voltar", callback_data="edit_templates")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
        return True

    elif data.startswith(("mudar_link_global_canal_", "mudar_link_bot_canal_", "mudar_link_externo_canal_")):
        canal_id = int(data.split("_")[-1])
        context.user_data['mudando_link_canal_id'] = canal_id
        if "global" in data:
            context.user_data['mudando_link_global_canal'] = True
            msg = "🌐 <b>Link Global do Canal</b>\n\nEnvie o novo link que substituirá TODOS os links:"
        elif "bot" in data:
            context.user_data['mudando_link_bot_canal'] = True
            msg = "🤖 <b>Link de Bot do Canal</b>\n\nEnvie o novo link do bot (ex: https://t.me/meubot):"
        else:
            context.user_data['mudando_link_externo_canal'] = True
            msg = "🔗 <b>Link Externo do Canal</b>\n\nEnvie o novo link que substituirá os links externos:"
            
        await query.edit_message_text(msg, parse_mode='HTML')
        return True

    elif data.startswith("edit_all_"):
        template_id = int(data.split("_")[-1])
        template = await get_template_with_link_ids(template_id)
        if not template: return True
        context.user_data['editing_all_links'] = True
        context.user_data['editing_template_id'] = template_id
        context.user_data['editing_num_links'] = len(template['links'])
        await query.edit_message_text(f"🔗 <b>Edição Global</b>\n\nEnvie o novo URL para todos os segmentos:", parse_mode='HTML')
        return True

    elif data == "edit_global_buttons":
        dados = context.user_data.get('editando', {})
        canal_id = dados.get('canal_id')
        if not canal_id: return True
        btns = await get_global_buttons(canal_id)
        msg = "🔘 <b>Botões Globais</b>\n\nEstes botões aparecem em todas as postagens do canal.\n\n"
        keyboard = []
        for b in btns:
            keyboard.append([InlineKeyboardButton(f"✏️ {b['text']}", callback_data=f"edit_global_button_{b['id']}"),
                            InlineKeyboardButton("🗑️", callback_data=f"deletar_global_button_{b['id']}")])
        keyboard.append([InlineKeyboardButton("➕ Adicionar Botão", callback_data=f"adicionar_global_button_{canal_id}")])
        keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar")])
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return True

    elif data.startswith("adicionar_global_button_"):
        canal_id = int(data.split("_")[-1])
        context.user_data.update({'adicionando_global_button': True, 'global_button_canal_id': canal_id, 'global_button_etapa': 'texto'})
        await query.edit_message_text("➕ <b>Novo Botão Global</b>\n\nEnvie o texto do botão:", parse_mode='HTML')
        return True

    elif data.startswith("edit_global_button_"):
        bid = int(data.split("_")[-1])
        # Aqui usamos o db_helpers para pegar info do botão global se existir, ou reusamos o de inline se for a mesma tabela
        # No bot-main original ele usava get_global_buttons e filtrava. 
        # Vou simplificar chamando a função de banco se houver, ou assumir o formato.
        # Na verdade, vou usar o get_global_buttons e achar o ID.
        canal_id = context.user_data['editando']['canal_id']
        btns = await get_global_buttons(canal_id)
        btn = next((b for b in btns if b['id'] == bid), None)
        if not btn: return True
        context.user_data.update({'editando_global_button': True, 'global_button_id': bid, 'global_button_canal_id': canal_id, 'global_button_etapa': 'texto'})
        await query.edit_message_text(f"✏️ <b>Editar Botão Global</b>\n\nTexto: '{btn['text']}'\nEnvie o novo texto:", parse_mode='HTML')
        return True

    elif data.startswith("deletar_global_button_"):
        bid = int(data.split("_")[-1])
        if await delete_global_button(bid):
            await query.answer("✅ Botão deletado!")
            await handle_edit_template_callback(query, context, parser) # Refresh
        return True

    elif data == "cancelar_global_button":
        for key in ['adicionando_global_button', 'editando_global_button']: context.user_data.pop(key, None)
        await handle_edit_template_callback(query, context, parser)
        return True

    elif data.startswith("adicionar_inline_button_"):
        template_id = int(data.split("_")[-1])
        context.user_data['adicionando_inline_button'] = True
        context.user_data['inline_button_template_id'] = template_id
        context.user_data['inline_button_etapa'] = 'texto'
        await query.edit_message_text("➕ <b>Adicionar Botão Inline</b>\n\nEnvie o texto do botão:", parse_mode='HTML')
        return True

    elif data.startswith("edit_inline_button_"):
        button_id = int(data.split("_")[-1])
        btn_info = await get_inline_button_info(button_id)
        if not btn_info: return True
        context.user_data['editando_inline_button'] = True
        context.user_data['inline_button_id'] = button_id
        context.user_data['inline_button_template_id'] = btn_info['template_id']
        context.user_data['inline_button_etapa'] = 'texto'
        await query.edit_message_text(f"✏️ <b>Editar Botão</b>\n\nTexto atual: '{btn_info['text']}'\nEnvie o novo texto:", parse_mode='HTML')
        return True

    elif data.startswith("deletar_inline_button_"):
        button_id = int(data.split("_")[-1])
        btn_info = await get_inline_button_info(button_id)
        if not btn_info: return True
        template_id = btn_info['template_id']
        if await delete_inline_button(button_id):
            await show_edit_panel(query, template_id, context, "✅ Botão inline deletado!")
        return True

    elif data.startswith("edit_link_"):
        link_id = int(data.split("_")[-1])
        link_info = await get_link_info(link_id)
        if not link_info: return True
        link_id_db, template_id, segmento, url_atual, ordem = link_info
        context.user_data['editing_link_id'] = link_id
        context.user_data['editing_template_id'] = template_id
        context.user_data['editing_segmento'] = segmento
        context.user_data['editing_ordem'] = ordem
        await query.edit_message_text(f"✏️ <b>Editando segmento {ordem}</b>\n\nSegmento: '{segmento}'\nEnvie o novo URL:", parse_mode='HTML')
        return True

    elif data == "confirmar_salvar_estatico":
        canal_id = context.user_data.get('canal_id_template')
        parsed = context.user_data.get('pending_template')
        if not canal_id or not parsed: return True
        template_id = await save_template(canal_id=canal_id, template_mensagem=parsed['template_mensagem'], links=[])
        await query.edit_message_text(f"✅ Template estático salvo (ID: {template_id})!", parse_mode='HTML')
        # Limpa
        for key in ['criando_template', 'etapa', 'pending_template']: context.user_data.pop(key, None)
        return True

    elif data.startswith("link_choice_"):
        choice = data.replace("link_choice_", "")
        canal_id = context.user_data.get('canal_id_template')
        parsed = context.user_data.get('pending_template')
        
        if choice == "keep":
            links = [(seg, url) for seg, url in zip(parsed['segmentos'], parsed['urls_originais'])]
            tid = await save_template(canal_id, parsed['template_mensagem'], links)
            await query.edit_message_text(f"✅ Template salvo com links originais (ID: {tid})!", parse_mode='HTML')
            for key in ['criando_template', 'etapa', 'pending_template']: context.user_data.pop(key, None)
        elif choice == "same":
            context.user_data['use_same_link'] = True
            context.user_data['etapa'] = 'recebendo_link'
            await query.edit_message_text("🔗 Envie o link único para todos os segmentos:", parse_mode='HTML')
        elif choice == "separate":
            context.user_data['etapa'] = 'recebendo_link'
            context.user_data['links_received'] = []
            context.user_data['current_link_index'] = 0
            await query.edit_message_text(f"🔗 Envie o link para o segmento '{parsed['segmentos'][0]}':", parse_mode='HTML')
        return True

    return False

async def handle_edit_template_message(update: Update, context: ContextTypes.DEFAULT_TYPE, parser):
    """Processa mensagens relacionadas a templates"""
    user_data = context.user_data
    message_text = update.message.text or update.message.caption or ""
    message_html = update.message.text_html or update.message.caption_html or message_text

    # Fluxo de Criação
    if user_data.get('criando_template'):
        etapa = user_data.get('etapa')
        canal_id = user_data.get('canal_id_template')
        
        if etapa == 'template_mensagem':
            parsed = parser.parse_and_save_template(message_html)
            user_data['pending_template'] = parsed
            user_data['original_message'] = message_html
            
            if parsed['num_links'] == 0:
                keyboard = [[InlineKeyboardButton("✅ Salvar", callback_data="confirmar_salvar_estatico")]]
                await update.message.reply_text("📝 Template estático detectado. Salvar?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
            else:
                keyboard = [
                    [InlineKeyboardButton("✅ Manter Originais", callback_data="link_choice_keep")],
                    [InlineKeyboardButton("🔗 Mesmo link para todos", callback_data="link_choice_same")],
                    [InlineKeyboardButton("🔗 Separados", callback_data="link_choice_separate")]
                ]
                await update.message.reply_text(f"✅ Localizei {parsed['num_links']} links. O que deseja fazer?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
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
                await update.message.reply_text(f"✅ Template salvo! ID: {tid}")
                for key in ['criando_template', 'etapa', 'pending_template', 'use_same_link']: user_data.pop(key, None)
            else:
                idx = user_data.get('current_link_index', 0)
                user_data['links_received'].append((parsed['segmentos'][idx], message_text.strip()))
                idx += 1
                user_data['current_link_index'] = idx
                
                if idx < len(parsed['segmentos']):
                    await update.message.reply_text(f"🔗 Envie o link para '{parsed['segmentos'][idx]}':")
                else:
                    tid = await save_template(canal_id, parsed['template_mensagem'], user_data['links_received'])
                    await update.message.reply_text(f"✅ Todos os links recebidos! Template ID: {tid}")
                    for key in ['criando_template', 'etapa', 'pending_template', 'links_received', 'current_link_index']: user_data.pop(key, None)
            return True

    # Fluxo de Edição
    if user_data.get('adicionando_inline_button'):
        tid = user_data['inline_button_template_id']
        if user_data['inline_button_etapa'] == 'texto':
            user_data['inline_button_text'] = message_text.strip()
            user_data['inline_button_etapa'] = 'url'
            await update.message.reply_text("✅ Texto salvo. Envie o URL:")
        else:
            url = message_text.strip()
            btns = await get_inline_buttons(tid)
            btns_list = [(b['text'], b['url']) for b in btns]
            btns_list.append((user_data['inline_button_text'], url))
            await save_inline_buttons(tid, btns_list)
            for key in ['adicionando_inline_button', 'inline_button_template_id', 'inline_button_etapa', 'inline_button_text']: user_data.pop(key, None)
            await show_edit_panel(update.message, tid, context, "✅ Botão adicionado!")
        return True

    if user_data.get('editando_inline_button'):
        bid = user_data['inline_button_id']
        tid = user_data['inline_button_template_id']
        if user_data['inline_button_etapa'] == 'texto':
            user_data['inline_button_new_text'] = message_text.strip()
            user_data['inline_button_etapa'] = 'url'
            await update.message.reply_text("✅ Novo texto salvo. Envie o novo URL:")
        else:
            url = message_text.strip()
            btns = await get_inline_buttons(tid)
            btns_list = [(b['text'], b['url']) for b in btns if b['id'] != bid]
            btns_list.append((user_data['inline_button_new_text'], url))
            await save_inline_buttons(tid, btns_list)
            for key in ['editando_inline_button', 'inline_button_id', 'inline_button_template_id', 'inline_button_etapa', 'inline_button_new_text']: user_data.pop(key, None)
            await show_edit_panel(update.message, tid, context, "✅ Botão atualizado!")
        return True

    if 'editing_all_links' in user_data:
        tid = user_data['editing_template_id']
        await update_all_links(tid, message_text.strip())
        for key in ['editing_all_links', 'editing_template_id', 'editing_num_links']: user_data.pop(key, None)
        await show_edit_panel(update.message, tid, context, "✅ Todos os links atualizados!")
        return True

    if 'editing_link_id' in user_data:
        lid = user_data['editing_link_id']
        tid = user_data['editing_template_id']
        await update_link(lid, message_text.strip())
        for key in ['editing_link_id', 'editing_template_id', 'editing_segmento', 'editing_ordem']: user_data.pop(key, None)
        await show_edit_panel(update.message, tid, context, "✅ Link atualizado!")
      # Fluxo de Mudar Link Global Canal
    if 'mudando_link_global_canal' in user_data:
        cid = user_data['mudando_link_canal_id']
        templates = await get_templates_by_canal(cid)
        for t in templates: await update_all_links(t['id'], message_text.strip())
        user_data.pop('mudando_link_global_canal', None)
        user_data.pop('mudando_link_canal_id', None)
        await update.message.reply_text("✅ Todos os links atualizados!")
        return True

    if user_data.get('adicionando_global_button'):
        cid = user_data['global_button_canal_id']
        if user_data['global_button_etapa'] == 'texto':
            user_data['global_button_text'] = message_text.strip()
            user_data['global_button_etapa'] = 'url'
            await update.message.reply_text("✅ Texto salvo. Envie o URL:")
        else:
            url = message_text.strip()
            btns = await get_global_buttons(cid)
            btns_list = [(b['text'], b['url']) for b in btns]
            btns_list.append((user_data['global_button_text'], url))
            await save_global_buttons(cid, btns_list)
            for key in ['adicionando_global_button', 'global_button_canal_id', 'global_button_etapa', 'global_button_text']: user_data.pop(key, None)
            await update.message.reply_text("✅ Botão global adicionado!")
        return True

    if user_data.get('editando_global_button'):
        bid = user_data['global_button_id']
        cid = user_data['global_button_canal_id']
        if user_data['global_button_etapa'] == 'texto':
            user_data['global_button_new_text'] = message_text.strip()
            user_data['global_button_etapa'] = 'url'
            await update.message.reply_text("✅ Novo texto salvo. Envie o novo URL:")
        else:
             url = message_text.strip()
             btns = await get_global_buttons(cid)
             btns_list = [(b['text'], b['url']) for b in btns if b['id'] != bid]
             btns_list.append((user_data['global_button_new_text'], url))
             await save_global_buttons(cid, btns_list)
             for key in ['editando_global_button', 'global_button_id', 'global_button_canal_id', 'global_button_etapa', 'global_button_new_text']: user_data.pop(key, None)
             await update.message.reply_text("✅ Botão global atualizado!")
        return True

    if 'mudando_link_bot_canal' in user_data:
        # A lógica completa de bot canal é longa, vou simplificar ou mover a parte de auxílio
        # Para preguiça do bot assistant, vou manter a lógica de loop aqui se for viável
        # Mas o usuário quer modularizar, então movemos a lógica completa.
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
        await update.message.reply_text("✅ Links de bot atualizados em todo o canal!")
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
        await update.message.reply_text("✅ Links externos atualizados em todo o canal!")
        return True

    return False
