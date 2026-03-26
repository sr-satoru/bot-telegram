import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from db_helpers import (
    get_all_admins, add_admin, remove_admin, get_admin, get_all_canais
)
from bot_utils import is_super_admin

logger = logging.getLogger(__name__)

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, super_admin_id: int):
    """Handlers de callback para o painel de administração"""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    
    if data == "gerenciar_admins":
        if not is_super_admin(user_id):
            await query.answer("❌ Apenas o super admin pode gerenciar admins.", show_alert=True)
            return True
        
        admins = await get_all_admins()
        
        mensagem = "👥 <b>Gerenciar Admins</b>\n\n"
        if not admins:
            mensagem += "Nenhum admin cadastrado."
        else:
            mensagem += "Admins cadastrados:\n\n"
            for admin in admins:
                username = admin['username'] or 'Sem username'
                aid = admin['user_id']
                mensagem += f"• ID: <code>{aid}</code> - @{username}\n"
        
        keyboard = [
            [InlineKeyboardButton("➕ Adicionar Admin", callback_data="adicionar_admin")],
            [InlineKeyboardButton("➖ Remover Admin", callback_data="remover_admin_lista")],
            [InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
        return True
    
    elif data == "adicionar_admin":
        if not is_super_admin(user_id):
            await query.answer("❌ Apenas o super admin pode adicionar admins.", show_alert=True)
            return True
        
        context.user_data['adicionando_admin'] = True
        await query.edit_message_text(
            "➕ <b>Adicionar Admin</b>\n\n"
            "Envie o ID do usuário que deseja adicionar como admin:",
            parse_mode='HTML'
        )
        return True
    
    elif data == "remover_admin_lista":
        if not is_super_admin(user_id):
            await query.answer("❌ Apenas o super admin pode remover admins.", show_alert=True)
            return True
        
        admins = await get_all_admins()
        if not admins:
            await query.answer("❌ Nenhum admin cadastrado.", show_alert=True)
            return True
        
        mensagem = "➖ <b>Remover Admin</b>\n\nSelecione o admin para remover:"
        keyboard = []
        for admin in admins:
            username = admin['username'] or 'Sem username'
            aid = admin['user_id']
            keyboard.append([
                InlineKeyboardButton(f"❌ {username} ({aid})", callback_data=f"remover_admin_{aid}")
            ])
        
        keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data="gerenciar_admins")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
        return True
    
    elif data.startswith("remover_admin_"):
        if not is_super_admin(user_id):
            await query.answer("❌ Apenas o super admin pode remover admins.", show_alert=True)
            return True
        
        admin_id = int(data.split("_")[-1])
        if admin_id == super_admin_id:
            await query.answer("❌ Não é possível remover o super admin.", show_alert=True)
            return True
        
        removed = await remove_admin(admin_id)
        if removed:
            await query.answer("✅ Admin removido com sucesso!", show_alert=True)
            # Reutiliza o handler para recarregar a lista
            query.data = "gerenciar_admins"
            await handle_admin_callback(update, context, super_admin_id)
        else:
            await query.answer("❌ Erro ao remover admin.", show_alert=True)
        return True
    
    elif data == "painel_controle":
        if not is_super_admin(user_id):
            await query.answer("❌ Apenas o super admin pode acessar o painel de controle.", show_alert=True)
            return True
        
        admins = await get_all_admins()
        all_canais = await get_all_canais()
        total_canais = len(all_canais)
        
        mensagem = "📊 <b>Painel de Controle</b>\n\n"
        mensagem += "📈 <b>Visão Geral</b>\n\n"
        mensagem += f"📢 Total de Canais: {total_canais}\n"
        mensagem += f"👥 Total de Admins: {len(admins)}\n\n"
        
        if admins:
            mensagem += "📋 <b>Canais por Admin:</b>\n\n"
            for admin in admins:
                aid = admin['user_id']
                username = admin['username'] or f"ID {aid}"
                admin_canais = await get_all_canais(user_id=aid)
                mensagem += f"👤 @{username} ({aid}): {len(admin_canais)} canal(is)\n"
        
        keyboard = []
        if admins:
            for admin in admins:
                aid = admin['user_id']
                username = admin['username'] or f"ID {aid}"
                keyboard.append([
                    InlineKeyboardButton(f"📊 Ver Canais de @{username}", callback_data=f"ver_canais_admin_{aid}")
                ])
        
        keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_start")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
        return True
    
    elif data.startswith("ver_canais_admin_"):
        if not is_super_admin(user_id):
            await query.answer("❌ Apenas o super admin pode ver isso.", show_alert=True)
            return True
        
        admin_id = int(data.split("_")[-1])
        admin_info = await get_admin(admin_id)
        if not admin_info:
            await query.answer("❌ Admin não encontrado.", show_alert=True)
            return True
        
        username = admin_info['username'] or f"ID {admin_id}"
        canais = await get_all_canais(user_id=admin_id)
        
        mensagem = f"📊 <b>Canais de @{username}</b>\n\n"
        if not canais:
            mensagem += "Nenhum canal cadastrado."
        else:
            for canal in canais:
                mensagem += f"📢 <b>{canal['nome']}</b> (ID: {canal['id']})\n"
                mensagem += f"   • Canais: {len(canal['ids'])}\n"
                mensagem += f"   • Horários: {len(canal['horarios'])}\n\n"
        
        keyboard = [[InlineKeyboardButton("⬅️ Voltar", callback_data="painel_controle")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
        return True
        
    return False

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE, super_admin_id: int):
    """Handle para adição de admins via mensagem"""
    if not context.user_data.get('adicionando_admin', False):
        return False
        
    user_id = update.effective_user.id
    message_text = update.message.text or ""
    
    if not is_super_admin(user_id):
        context.user_data.pop('adicionando_admin', None)
        await update.message.reply_text("❌ Você não tem permissão para adicionar admins.")
        return True
    
    try:
        admin_id = int(message_text.strip())
        if admin_id == super_admin_id:
            await update.message.reply_text("❌ O super admin já tem todas as permissões.")
            context.user_data.pop('adicionando_admin', None)
            return True
        
        try:
            user_info = await context.bot.get_chat(admin_id)
            username = user_info.username
        except:
            username = None
        
        success = await add_admin(admin_id, username)
        if success:
            context.user_data.pop('adicionando_admin', None)
            await update.message.reply_text(
                f"✅ <b>Admin adicionado com sucesso!</b>\n\n"
                f"ID: {admin_id} - @{username if username else 'Sem username'}\n\n"
                f"O usuário agora pode usar o bot.",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("⚠️ Este usuário já é admin ou ocorreu um erro ao adicionar.")
            
    except ValueError:
        await update.message.reply_text("❌ ID inválido. Por favor, envie apenas números.")
        
    return True
