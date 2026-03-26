import os
import logging
from datetime import datetime
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from db_helpers import is_admin_db

logger = logging.getLogger(__name__)

# ID do super admin
SUPER_ADMIN = os.getenv('SUPER_ADMIN')
if not SUPER_ADMIN:
    SUPER_ADMIN_ID = None
else:
    try:
        SUPER_ADMIN_ID = int(SUPER_ADMIN)
    except ValueError:
        SUPER_ADMIN_ID = None

def is_super_admin(user_id: int) -> bool:
    """Verifica se o usuário é o super admin"""
    return user_id == SUPER_ADMIN_ID

# Cache de admins (user_id: timestamp)
_admin_cache = {}
_cache_ttl = 300 # 5 minutos

async def is_admin(user_id: int) -> bool:
    """Verifica se o usuário é admin (super admin ou admin normal) com cache"""
    if is_super_admin(user_id):
        return True
    
    now = datetime.now().timestamp()
    if user_id in _admin_cache:
        cached_val, ts = _admin_cache[user_id]
        if now - ts < _cache_ttl:
            return cached_val
            
    res = await is_admin_db(user_id)
    _admin_cache[user_id] = (res, now)
    return res

async def is_admin_only(user_id: int) -> bool:
    """Verifica se o usuário é apenas admin (não super admin)"""
    return await is_admin(user_id) and not is_super_admin(user_id)

def require_admin(func):
    """Decorador que verifica se o usuário é admin ou super admin antes de executar a função"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return
            
        if await is_admin(user.id):
            return await func(update, context, *args, **kwargs)
        else:
            message_text = "❌ Você não tem permissão para usar este bot. Fale com o @sr_satoru_Gojo para liberar seu acesso"
            if update.callback_query:
                await update.callback_query.answer(message_text, show_alert=True)
            elif update.message:
                await update.message.reply_text(message_text)
                
    return wrapper

def require_super_admin(func):
    """Decorador que verifica se o usuário é super admin antes de executar a função"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return
            
        if is_super_admin(user.id):
            return await func(update, context, *args, **kwargs)
        else:
            message_text = "❌ Você não tem permissão para usar este bot."
            if update.callback_query:
                await update.callback_query.answer(message_text, show_alert=True)
            elif update.message:
                await update.message.reply_text(message_text)
                
    return wrapper
