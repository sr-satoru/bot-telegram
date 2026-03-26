from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

async def mostrar_menu_ids(query, context):
    """Mostra o menu de gerenciamento de IDs"""
    dados = context.user_data.get('editando', {})
    ids = dados.get('ids', [])
    
    mensagem = "🆔 <b>Gerenciar IDs</b>\n\n"
    
    if ids:
        mensagem += "<b>IDs configurados:</b>\n"
        for i, canal_id_str in enumerate(ids, 1):
            try:
                canal_id_int = int(canal_id_str)
                try:
                    chat = await context.bot.get_chat(canal_id_int)
                    chat_title = chat.title or chat.username or f"Canal {canal_id_str}"
                    mensagem += f"{i}. <code>{canal_id_str}</code> - {chat_title}\n"
                except Exception:
                    mensagem += f"{i}. <code>{canal_id_str}</code>\n"
            except ValueError:
                mensagem += f"{i}. <code>{canal_id_str}</code>\n"
    else:
        mensagem += "❌ Nenhum ID configurado\n"
    
    mensagem += f"\nTotal: {len(ids)} ID(s)"
    
    keyboard = [
        [
            InlineKeyboardButton("➕ Adicionar ID", callback_data="edit_add_id"),
        ],
    ]
    
    if ids:
        keyboard.append([
            InlineKeyboardButton("🗑 Remover ID", callback_data="edit_remove_id"),
        ])
    
    keyboard.append([
        InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar"),
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')

async def handle_edit_ids_callback(query, context):
    """Handlers de callback para gerenciamento de IDs"""
    data = query.data
    
    if data == "edit_ids":
        await mostrar_menu_ids(query, context)
        return True
        
    elif data == "edit_add_id":
        # Inicia adição de ID
        context.user_data['editando']['etapa'] = 'adicionando_id'
        
        keyboard = [
            [
                InlineKeyboardButton("❌ Cancelar", callback_data="edit_voltar"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🆔 <b>Adicionar ID</b>\n\nEnvie o ID do Telegram do canal:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return True
        
    elif data == "edit_remove_id":
        # Mostra lista de IDs para remover
        dados = context.user_data.get('editando', {})
        ids = dados.get('ids', [])
        
        if not ids:
            await query.edit_message_text(
                "⚠️ Nenhum ID para remover.",
                parse_mode='HTML'
            )
            return True
        
        keyboard = []
        for i, canal_id in enumerate(ids):
            keyboard.append([
                InlineKeyboardButton(f"❌ {canal_id}", callback_data=f"edit_remove_id_{i}")
            ])
        
        keyboard.append([
            InlineKeyboardButton("⬅️ Voltar", callback_data="edit_ids"),
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🗑 <b>Remover ID</b>\n\nSelecione o ID para remover:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return True
        
    elif data.startswith("edit_remove_id_"):
        # Remove um ID específico
        index = int(data.split("_")[-1])
        dados = context.user_data.get('editando', {})
        ids = dados.get('ids', [])
        
        if 0 <= index < len(ids):
            ids.pop(index)
            dados['ids'] = ids
            dados['changes_made'] = True
            
            await mostrar_menu_ids(query, context)
        return True
        
    return False

async def handle_edit_ids_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa ID enviado pelo usuário"""
    if 'editando' not in context.user_data:
        return False
        
    dados = context.user_data['editando']
    etapa = dados.get('etapa')
    
    if etapa == 'adicionando_id':
        message_text = update.message.text
        # Adiciona novo ID
        try:
            telegram_id = int(message_text.strip())
            
            # Verifica se o bot é admin
            try:
                bot_member = await context.bot.get_chat_member(
                    chat_id=telegram_id,
                    user_id=context.bot.id
                )
                
                is_admin = (
                    bot_member.status == 'administrator' or 
                    bot_member.status == 'creator'
                )
                
                if not is_admin:
                    await update.message.reply_text(
                        f"❌ Bot não é admin do canal <code>{telegram_id}</code>",
                        parse_mode='HTML'
                    )
                    return True
                
                # Busca o nome do canal/grupo
                try:
                    chat = await context.bot.get_chat(telegram_id)
                    chat_title = chat.title or chat.username or f"Canal {telegram_id}"
                except Exception:
                    chat_title = f"Canal {telegram_id}"
                
                # Verifica se o ID já existe
                ids = dados.get('ids', [])
                if str(telegram_id) in ids:
                    await update.message.reply_text(
                        f"⚠️ ID <code>{telegram_id}</code> já foi adicionado.\n\n" +
                        "IDs atuais:\n" +
                        "\n".join([f"<code>{cid}</code>" for cid in ids]),
                        parse_mode='HTML'
                    )
                    return True
                
                # Adiciona o ID
                ids.append(str(telegram_id))
                dados['ids'] = ids
                dados['changes_made'] = True
                del dados['etapa']
                
                # Envia mensagem e mostra menu de IDs
                await update.message.reply_text(
                    f"✅ ID <code>{telegram_id}</code> adicionado!\n"
                    f"📝 <b>Nome:</b> {chat_title}",
                    parse_mode='HTML'
                )
                
                # Mostra menu de IDs usando um objeto query simulado ou chamando a função
                # Para simplificar aqui, vamos apenas recriar a mensagem do menu ou 
                # chamar o mostrar_menu_ids se tivéssemos um query.
                # Como estamos em handle_message, o ideal é enviar uma NOVA mensagem com o menu.
                
                # Vamos simplificar enviando uma nova mensagem com o menu
                # Mas para isso precisamos do objeto query que não temos aqui.
                # Então vamos apenas informar o sucesso e o usuário clica no menu anterior ou volta.
                # Na verdade, o código original tentava editar a mensagem anterior, mas em handle_message 
                # ele enviava uma nova e depois editava e tal. 
                # Vou manter a lógica original o mais fiel possível.
                
                # No bot-main original:
                # msg = await update.message.reply_text(...)
                # await msg.edit_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
                
                # Vou criar um helper interno ou apenas repetir o código do menu aqui.
                
                # Reutilizando a lógica do menu (repetida por brevidade ou extraída)
                mensagem = "🆔 <b>Gerenciar IDs</b>\n\n"
                mensagem += "<b>IDs configurados:</b>\n"
                for i, cid in enumerate(ids, 1):
                     mensagem += f"{i}. <code>{cid}</code>\n"
                
                keyboard = [
                    [InlineKeyboardButton("➕ Adicionar ID", callback_data="edit_add_id")],
                    [InlineKeyboardButton("🗑 Remover ID", callback_data="edit_remove_id")],
                    [InlineKeyboardButton("⬅️ Voltar", callback_data="edit_voltar")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
                
            except Exception as e:
                error_msg = str(e).lower()
                if 'chat not found' in error_msg or 'not found' in error_msg:
                    await update.message.reply_text(
                        f"❌ Canal <code>{telegram_id}</code> não encontrado.",
                        parse_mode='HTML'
                    )
                else:
                    await update.message.reply_text(
                        f"❌ Erro: {str(e)[:100]}",
                        parse_mode='HTML'
                    )
                    
        except ValueError:
            await update.message.reply_text(
                "⚠️ ID inválido. Envie um número.",
                parse_mode='HTML'
            )
        return True
        
    return False
