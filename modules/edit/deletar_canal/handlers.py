import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from db_helpers import get_canal, delete_canal
from bot_utils import is_super_admin

logger = logging.getLogger(__name__)

async def handle_deletar_canal_callback(query, context, mostrar_menu_edicao_callback):
    """Handlers de callback para exclusão de canais"""
    data = query.data
    user_id = query.from_user.id
    
    if data == "edit_deletar_canal":
        # Confirmação para deletar canal
        dados = context.user_data.get('editando', {})
        
        if not dados:
            await query.answer("❌ Erro: dados não encontrados.", show_alert=True)
            return True
        
        canal_id = dados.get('canal_id')
        nome_canal = dados.get('nome', 'Canal')
        
        # Verifica permissão
        canal = await get_canal(canal_id)
        if not canal:
            await query.answer("❌ Canal não encontrado.", show_alert=True)
            return True
        
        if not is_super_admin(user_id) and canal['user_id'] != user_id:
            await query.answer("❌ Você não tem permissão para deletar este canal.", show_alert=True)
            return True
        
        # Mostra confirmação
        mensagem = f"⚠️ <b>Confirmar Exclusão</b>\n\n"
        mensagem += f"Tem certeza que deseja <b>DELETAR</b> o canal:\n\n"
        mensagem += f"📢 <b>{nome_canal}</b>\n\n"
        mensagem += f"<b>Esta ação não pode ser desfeita!</b>\n\n"
        mensagem += f"❌ Serão deletados:\n"
        mensagem += f"• Canal e configurações\n"
        mensagem += f"• Todos os templates\n"
        mensagem += f"• Todos os grupos de mídias\n"
        mensagem += f"• Todas as configurações relacionadas\n"
        
        keyboard = [
            [
                InlineKeyboardButton("❌ Confirmar Deletar", callback_data=f"confirmar_deletar_canal_{canal_id}"),
            ],
            [
                InlineKeyboardButton("⬅️ Cancelar", callback_data="cancelar_deletar_canal"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
        return True
    
    elif data.startswith("confirmar_deletar_canal_"):
        # Confirma e deleta o canal
        canal_id = int(data.split("_")[-1])
        
        # Verifica permissão novamente
        canal = await get_canal(canal_id)
        if not canal:
            await query.answer("❌ Canal não encontrado.", show_alert=True)
            return True
        
        if not is_super_admin(user_id) and canal['user_id'] != user_id:
            await query.answer("❌ Você não tem permissão para deletar este canal.", show_alert=True)
            return True
        
        nome_canal = canal['nome']
        
        # Deleta o canal
        deleted = await delete_canal(canal_id)
        
        if deleted:
            # Limpa contexto de edição
            if 'editando' in context.user_data:
                del context.user_data['editando']
            
            # Mensagem de sucesso com botão para voltar ao menu
            keyboard = [
                [
                    InlineKeyboardButton("⬅️ Voltar ao Menu", callback_data="voltar_start"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"✅ <b>Canal deletado com sucesso!</b>\n\n"
                f"📢 <b>{nome_canal}</b> foi permanentemente removido.\n\n"
                f"Todos os dados relacionados foram excluídos.",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await query.answer("❌ Erro ao deletar canal.", show_alert=True)
        return True
    
    elif data == "cancelar_deletar_canal":
        # Cancela a deleção e volta para o menu de edição
        await mostrar_menu_edicao_callback(query, context)
        return True
        
    return False
