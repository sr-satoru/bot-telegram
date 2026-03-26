from telegram import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import ContextTypes
from modules.utils import strip_html_tags

async def mostrar_lista_templates(obj, templates, canal_id, context: ContextTypes.DEFAULT_TYPE, extra_text=""):
    """Exibe a lista de templates do canal"""
    mensagem = extra_text or "📝 <b>Gerenciar Templates</b>\n\n"
    if not templates:
        keyboard = [
            [InlineKeyboardButton("➕ Adicionar Template", callback_data=f"adicionar_template_{canal_id}")],
            [InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar")]
        ]
        mensagem += "❌ Nenhum template encontrado."
    else:
        mensagem += f"Total: {len(templates)} template(s)\n\n"
        keyboard = []
        for template in templates:
            tid = template['id']
            msg = template['template_mensagem']
            clean_msg = strip_html_tags(msg)
            preview = clean_msg[:25] + "..." if len(clean_msg) > 25 else clean_msg
            keyboard.append([
                InlineKeyboardButton(f"📄 {preview}", callback_data=f"edit_template_{tid}"),
                InlineKeyboardButton("👁️ Preview", callback_data=f"preview_template_{tid}")
            ])
            keyboard.append([
                InlineKeyboardButton("🗑️ Deletar", callback_data=f"deletar_template_{tid}")
            ])
        
        keyboard.append([InlineKeyboardButton("➕ Adicionar Template", callback_data=f"adicionar_template_{canal_id}")])
        keyboard.append([InlineKeyboardButton("🔗 Mudar link geral", callback_data=f"mudar_link_geral_canal_{canal_id}")])
        keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    if isinstance(obj, CallbackQuery):
        await obj.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await obj.reply_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')

async def mostrar_preview_template(obj, template, global_buttons, parser, context: ContextTypes.DEFAULT_TYPE):
    """Mostra o preview formatado de um template"""
    template_id = template['id']
    template_mensagem = template['template_mensagem']
    links = template['links']
    inline_buttons = template.get('inline_buttons', [])
    
    links_tuples = [(link['segmento'], link['link']) for link in links]
    formatted_message = parser.format_message_with_links(template_mensagem, links_tuples)
    
    preview_text = f"👁️ <b>Preview - Template ID: {template_id}</b>\n\n"
    preview_text += f"📄 <b>Mensagem formatada:</b>\n\n"
    preview_text += formatted_message
    
    preview_keyboard = []
    all_buttons = []
    
    if global_buttons:
        preview_text += f"\n\n🔘 <b>Botões Globais ({len(global_buttons)}):</b>\n"
        for button in global_buttons:
            preview_text += f"• 🌐 {button['text']} → {button['url'][:30]}...\n"
            all_buttons.append(InlineKeyboardButton(button['text'], url=button['url']))
    
    if inline_buttons:
        preview_text += f"\n🔘 <b>Botões do Template ({len(inline_buttons)}):</b>\n"
        for button in inline_buttons:
            preview_text += f"• {button['text']} → {button['url'][:30]}...\n"
            all_buttons.append(InlineKeyboardButton(button['text'], url=button['url']))
            
    if all_buttons:
        row = []
        for btn in all_buttons:
            row.append(btn)
            if len(row) >= 2:
                preview_keyboard.append(row); row = []
        if row: preview_keyboard.append(row)
        
    preview_keyboard.append([
        InlineKeyboardButton("⬅️ Voltar", callback_data="edit_templates"),
        InlineKeyboardButton("✏️ Editar", callback_data=f"edit_template_{template_id}")
    ])
    
    reply_markup = InlineKeyboardMarkup(preview_keyboard)
    if isinstance(obj, CallbackQuery):
        await obj.edit_message_text(preview_text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await obj.reply_text(preview_text, reply_markup=reply_markup, parse_mode='HTML')

async def mostrar_painel_edicao_links(obj, template, inline_buttons, context: ContextTypes.DEFAULT_TYPE, success_message=""):
    """Mostra o painel de edição de links de um template"""
    template_id = template['id']
    links = template['links']
    
    mensagem = f"🔧 <b>Configuração de Links - ID: {template_id}</b>\n\n"
    if success_message: mensagem += f"{success_message}\n\n"
        
    mensagem += "📄 <b>Texto:</b>\n"
    t_msg = template['template_mensagem']
    clean_t_msg = strip_html_tags(t_msg)
    preview = clean_t_msg[:100] + "..." if len(clean_t_msg) > 100 else clean_t_msg
    mensagem += f"<i>{preview}</i>\n\n"
    mensagem += f"🔗 <b>Segmentos identificados ({len(links)}):</b>\n"
    
    keyboard = []
    for link_id, segmento, url, ordem in links:
        url_display = url if len(url) <= 30 else url[:27] + "..."
        mensagem += f"{ordem}. '{segmento}'\n   → {url_display}\n\n"
        keyboard.append([InlineKeyboardButton(f"✏️ Editar {ordem}", callback_data=f"edit_link_{link_id}")])
    
    if inline_buttons:
        mensagem += "\n🔘 <b>Botões Inline:</b>\n"
        for i, button in enumerate(inline_buttons, 1):
            url_display = button['url'] if len(button['url']) <= 30 else button['url'][:27] + "..."
            status_icon = "🟢" if button.get('status') == "ATIVO" else "🔴"
            mensagem += f"{i}. '{button['text']}' ({status_icon}) → {url_display}\n"
            keyboard.append([
                InlineKeyboardButton(f"✏️ Botão {i}", callback_data=f"fix_button_tg_edit_{button['id']}"),
                InlineKeyboardButton("🗑️", callback_data=f"fix_button_tg_del_{button['id']}")
            ])
            
    keyboard.append([InlineKeyboardButton("🔘 Gerenciar Botões do Template (Fixos)", callback_data=f"fix_button_tg_list_{template_id}")])
    keyboard.append([InlineKeyboardButton("🔄 Mudar Todos os Links", callback_data=f"edit_all_{template_id}")])
    keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data="edit_templates")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    if isinstance(obj, CallbackQuery):
        await obj.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await obj.reply_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')

async def mostrar_confirmacao_delecao(query, template_id, preview_msg):
    """Mostra o menu de confirmação de deleção"""
    mensagem = f"🗑️ <b>Deletar Template?</b>\n\n📝 ID: {template_id}\n📄 {preview_msg}\n\n⚠️ Esta ação não pode ser desfeita!"
    keyboard = [[
        InlineKeyboardButton("✅ Confirmar", callback_data=f"confirmar_deletar_template_{template_id}"),
        InlineKeyboardButton("❌ Cancelar", callback_data="edit_templates")
    ]]
    await query.edit_message_text(mensagem, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def mostrar_menu_tipo_link_geral(query, canal_id, num_templates):
    """Mostra opções para mudar links em todo o canal"""
    mensagem = "🔄 <b>Mudar Link Geral do Canal</b>\n\n"
    mensagem += f"⚠️ Esta ação afetará <b>TODOS os {num_templates} template(s)</b> do canal.\n\n"
    mensagem += "Escolha como os links devem ser alterados:"
    keyboard = [
        [InlineKeyboardButton("🌐 Link global", callback_data=f"mudar_link_global_canal_{canal_id}")],
        [InlineKeyboardButton("🤖 Link de bot", callback_data=f"mudar_link_bot_canal_{canal_id}")],
        [InlineKeyboardButton("🔗 Link externo", callback_data=f"mudar_link_externo_canal_{canal_id}")],
        [InlineKeyboardButton("⬅️ Voltar", callback_data="edit_templates")]
    ]
    await query.edit_message_text(mensagem, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

async def mostrar_prompt_criacao_template(obj):
    """Prompt inicial para novo template"""
    mensagem = (
        "📝 <b>Adicionar Template</b>\n\n"
        "Envie a mensagem usando a formatação do Telegram:\n"
        "• Use <b>negrito</b>, <i>itálico</i>, <u>sublinhado</u>, etc.\n"
        "• Use <b>Inserir Link</b> (hiperlink) no próprio texto.\n\n"
        "O bot identificará todos os links e a formatação automaticamente! ✅"
    )
    if isinstance(obj, CallbackQuery):
        await obj.edit_message_text(mensagem, parse_mode='HTML')
    else:
        await obj.reply_text(mensagem, parse_mode='HTML')

async def mostrar_escolha_link_template(message, num_links):
    """Pergunta o que fazer com os links encontrados"""
    keyboard = [
        [InlineKeyboardButton("✅ Manter Originais", callback_data="link_choice_keep")],
        [InlineKeyboardButton("🔗 Mesmo link para todos", callback_data="link_choice_same")],
        [InlineKeyboardButton("🔗 Separados", callback_data="link_choice_separate")]
    ]
    await message.reply_text(
        f"✅ Localizei {num_links} links. O que deseja fazer?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def mostrar_prompt_link_estatico(message):
    """Prompt para template sem links"""
    keyboard = [[InlineKeyboardButton("✅ Salvar", callback_data="confirmar_salvar_estatico")]]
    await message.reply_text(
        "📝 Template estático detectado (sem links dinâmicos). Salvar?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def mostrar_prompt_edicao_global(query, num_links):
    """Prompt para edição de todos os links de um template"""
    mensagem = f"🔗 <b>Edição Global</b>\n\nEnvie o novo URL que substituirá todos os {num_links} segmentos:"
    await query.edit_message_text(mensagem, parse_mode='HTML')

async def mostrar_prompt_mudar_link_canal(query, tipo):
    """Prompts para mudança de link em todo o canal"""
    prompts = {
        'global': "🌐 <b>Link Global do Canal</b>\n\nEnvie o novo link que substituirá TODOS os links:",
        'bot': "🤖 <b>Link de Bot do Canal</b>\n\nEnvie o novo link do bot (ex: https://t.me/meubot):",
        'externo': "🔗 <b>Link Externo do Canal</b>\n\nEnvie o novo link que substituirá os links externos:"
    }
    await query.edit_message_text(prompts.get(tipo, "Envie o novo link:"), parse_mode='HTML')

async def mostrar_erro_template(obj, erro="Template não encontrado."):
    """Função genérica para exibir erros de template"""
    mensagem = f"❌ {erro}"
    if isinstance(obj, CallbackQuery):
        await obj.edit_message_text(mensagem, parse_mode='HTML')
    else:
        await obj.reply_text(mensagem, parse_mode='HTML')
