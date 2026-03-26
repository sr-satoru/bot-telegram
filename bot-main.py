import os
import logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Configuração de Timezone
try:
    from zoneinfo import ZoneInfo
    BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")
except ImportError:
    from datetime import timezone, timedelta
    BRASILIA_TZ = timezone(timedelta(hours=-3))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import Conflict

# Módulos Internos
from db import prisma
from modules.utils import require_admin, is_super_admin
from modules.ui import mostrar_menu_inicial_msg, mostrar_menu_inicial_query, mostrar_menu_edicao
from modules.criar_canal import handle_criar_canal_callback, handle_criar_canal_message
from modules.edit.editar_nome import handle_edit_nome_callback, handle_edit_nome_message
from modules.edit.gerenciar_id import handle_edit_ids_callback, handle_edit_ids_message
from modules.edit.gerenciar_time import handle_edit_time_callback, handle_edit_time_message
from modules.edit.gerenciar_template import handle_edit_template_callback, handle_edit_template_message
from modules.edit.gerenciar_midias import handle_edit_media_callback, handle_edit_media_input, finalizar_grupo
from modules.edit.deletar_canal import handle_deletar_canal_callback
from modules.buton_global.handlers import handle_global_button_callback, handle_global_button_message
from modules.admin import handle_admin_callback, handle_admin_message
from db_helpers import get_canal, get_all_canais, update_canal
from modules.capture_parse_mode import MessageParser
from media_handler import MediaHandler
from modules.post import MediaScheduler
from setcomando import set_bot_commands

# Carrega ambiente
load_dotenv()
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
SUPER_ADMIN_ID = int(os.getenv('SUPER_ADMIN', 0))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN não encontrado no .env")

parser = MessageParser()
media_handler = MediaHandler()

@require_admin
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu Inicial"""
    user_id = update.effective_user.id
    # Limpa contexto de fluxos pendentes
    for key in list(context.user_data.keys()):
        context.user_data.pop(key, None)
    await mostrar_menu_inicial_msg(update.message, user_id)

@require_admin
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Roteador de Callbacks"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    # 1. Delegações de Módulos (Ordem importa)
    if await handle_criar_canal_callback(query, context): return
    if await handle_admin_callback(query, context, SUPER_ADMIN_ID): return
    if await handle_global_button_callback(query, context): return
    if await handle_edit_template_callback(query, context, parser): return
    if await handle_edit_media_callback(query, context, media_handler, prisma): return
    if await handle_edit_nome_callback(query, context): return
    if await handle_edit_ids_callback(query, context): return
    if await handle_edit_time_callback(query, context): return
    if await handle_deletar_canal_callback(query, context): return

    # 2. Navegação Principal em bot-main.py
    if data == "editar_canal":
        canais = await get_all_canais(user_id=user_id)
        if not canais:
            await query.edit_message_text("📭 Nenhum canal encontrado.\nCrie um primeiro.", parse_mode='HTML')
            return
        keyboard = [[InlineKeyboardButton(f"📢 {c['nome']}", callback_data=f"editar_canal_{c['id']}")] for c in canais]
        keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_start")])
        await query.edit_message_text("✏️ <b>Editar Canal</b>\n\nSelecione um canal:", 
                                     reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
    
    elif data == "voltar_start":
        await mostrar_menu_inicial_query(query, user_id)
    
    elif data.startswith("editar_canal_"):
        canal_id = int(data.split("_")[-1])
        canal = await get_canal(canal_id)
        if not canal or (not is_super_admin(user_id) and canal['user_id'] != user_id):
            await query.edit_message_text("❌ Sem permissão ou canal inexistente.", parse_mode='HTML')
            return
        context.user_data['editando'] = {
            'canal_id': canal_id, 'nome': canal['nome'], 
            'ids': canal['ids'].copy(), 'horarios': canal['horarios'].copy(), 
            'changes_made': False
        }
        await mostrar_menu_edicao(query, context)

    elif data == "edit_voltar":
        await mostrar_menu_edicao(query, context)

    elif data == "edit_cancelar":
        context.user_data.pop('editando', None)
        await query.edit_message_text("❌ Edição cancelada.", parse_mode='HTML')

    elif data == "edit_salvar":
        dados = context.user_data.get('editando')
        if not dados or not dados.get('changes_made', False):
            await query.answer("ℹ️ Nenhuma alteração para salvar.")
            return

        await update_canal(canal_id=dados['canal_id'], nome=dados.get('nome'), 
                          ids_canal=dados.get('ids'), horarios=dados.get('horarios'))
        
        # Reset flag de mudanças e mostra menu novamente com mensagem de sucesso
        dados['changes_made'] = False
        success_msg = "✅ <b>Alterações salvas com sucesso!</b>\n\n"
        await mostrar_menu_edicao(query, context, extra_text=success_msg)

@require_admin
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Roteador de Mensagens"""
    # Delegações de Módulos (Ordem importa)
    if await handle_admin_message(update, context, SUPER_ADMIN_ID): return
    if 'editando' in context.user_data:
        if await handle_edit_nome_message(update, context): return
        if await handle_edit_ids_message(update, context): return
        if await handle_edit_time_message(update, context): return
    if await handle_criar_canal_message(update, context): return
    if await handle_edit_template_message(update, context, parser): return
    if await handle_edit_media_input(update, context, media_handler): return
    if await handle_global_button_message(update, context): return

@require_admin
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Roteador de Mídias"""
    if await handle_edit_media_input(update, context, media_handler):
        return

# Inicialização e Eventos
async def post_init(app: Application) -> None:
    await prisma.connect()
    await set_bot_commands(app)
    app.bot_data['scheduler'] = MediaScheduler(media_handler, app.bot)
    import asyncio
    asyncio.create_task(app.bot_data['scheduler'].run_scheduler())
    logger.info("🚀 Scheduler iniciado!")

async def post_shutdown(app: Application) -> None:
    await prisma.disconnect()
    logger.info("🔌 Prisma desconectado.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(context.error, Conflict):
        return # Silencia conflitos de polling
    logger.error(f"Erro: {context.error}", exc_info=context.error)

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()
    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("finalizar_grupo", finalizar_grupo))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, handle_media))
    
    logger.info("Bot Iniciado!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
