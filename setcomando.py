"""
Módulo para definir comandos do bot programaticamente
"""
from telegram import BotCommand
from telegram.ext import Application
import logging

logger = logging.getLogger(__name__)

# Comandos padrão do bot
COMANDOS_PADRAO = [
    BotCommand("start", "🚀 Inicia o bot"),
]

async def set_bot_commands(application: Application):
    """
    Define os comandos do bot programaticamente.
    
    Args:
        application: Instância da Application do telegram.ext
    """
    try:
        # Chama a API do Telegram para definir os comandos
        await application.bot.set_my_commands(COMANDOS_PADRAO)
        logger.info("✅ Comandos do bot definidos com sucesso!")
        
        # Log dos comandos definidos
        comandos_str = ", ".join([f"/{cmd.command}" for cmd in COMANDOS_PADRAO])
        logger.info(f"📋 Comandos registrados: {comandos_str}")
    except Exception as e:
        logger.error(f"❌ Erro ao definir comandos do bot: {e}")
