import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from db_helpers import save_canal, get_all_canais, get_canal
# Importa o utilitário compartilhado de horários
from modules.edit.gerenciar_time.utils import validar_horario, mostrar_painel_horarios

logger = logging.getLogger(__name__)

async def handle_criar_canal_callback(query, context):
    """Processa todos os callbacks relacionados à criação de canal"""
    data = query.data
    user_id = query.from_user.id

    if data == "criar_canal":
        context.user_data.update({'criando_canal': True, 'etapa': 'nome', 'ids_canal': [], 'horarios': []})
        await query.edit_message_text("📢 <b>Criar Canal</b>\n\nEnvie o nome:", parse_mode='HTML')
        return True

    elif data == "adicionar_outro_id":
        context.user_data['etapa'] = 'id'
        await query.edit_message_text("📢 <b>Adicionar ID</b>\n\nEnvie o ID:", 
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_adicionar_id")]]), 
                                     parse_mode='HTML')
        return True

    elif data == "cancelar_adicionar_id":
        await mostrar_confirmacao_ids(query, context)
        return True

    elif data == "confirmar_canal":
        context.user_data['etapa'] = 'horarios'
        await mostrar_painel_horarios(query, context, is_edicao=False)
        return True

    elif data == "adicionar_horario":
        context.user_data['etapa'] = 'adicionando_horario'
        await query.edit_message_text("🕒 <b>Adicionar Horário</b>\n\nEnvie os horários (HH:MM, ...):", 
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="voltar_menu_horarios")]]), 
                                     parse_mode='HTML')
        return True

    elif data == "remover_horario":
        horarios = sorted(context.user_data.get('horarios', []))
        if not horarios: return True
        keyboard = [[InlineKeyboardButton(f"❌ {h}", callback_data=f"remove_h_{i}")] for i, h in enumerate(horarios)]
        keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data="voltar_menu_horarios")])
        await query.edit_message_text("🗑 Selecione para remover:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return True

    elif data.startswith("remove_h_"):
        idx = int(data.split("_")[-1])
        horarios = sorted(context.user_data.get('horarios', []))
        if 0 <= idx < len(horarios):
            context.user_data['horarios'].remove(horarios[idx])
            await mostrar_painel_horarios(query, context, is_edicao=False)
        return True

    elif data == "voltar_menu_horarios":
        await mostrar_painel_horarios(query, context, is_edicao=False)
        return True

    elif data == "confirmar_horarios":
        u = context.user_data
        cid = await save_canal(nome=u['nome_canal'], user_id=user_id, ids_canal=u['ids_canal'], horarios=u['horarios'])
        for k in ['criando_canal', 'etapa', 'nome_canal', 'ids_canal', 'horarios']: u.pop(k, None)
        await query.edit_message_text(f"✅ <b>Canal criado!</b> (ID: {cid})", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Finalizar", callback_data="voltar_start")]]), parse_mode='HTML')
        return True
    
    elif data == "cancelar_criar_canal":
        from modules.ui import mostrar_menu_inicial_query
        await mostrar_menu_inicial_query(query, user_id)
        return True

    return False

async def mostrar_confirmacao_ids(obj, context, extra_text=""):
    u = context.user_data
    mensagem = extra_text + f"✅ <b>Canal: {u['nome_canal']}</b>\n\nIDs ({len(u['ids_canal'])}):\n" + "\n".join([f"• <code>{i}</code>" for i in u['ids_canal']])
    keyboard = [[InlineKeyboardButton("➕ Adicionar outro ID", callback_data="adicionar_outro_id")],
                [InlineKeyboardButton("✅ Confirmar", callback_data="confirmar_canal")]]
    from telegram import CallbackQuery
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if isinstance(obj, CallbackQuery):
        await obj.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await obj.reply_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')

async def handle_criar_canal_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = context.user_data
    if not u.get('criando_canal'): return False
    text = update.message.text.strip()
    etapa = u.get('etapa')

    if etapa == 'nome':
        u.update({'nome_canal': text, 'etapa': 'id'})
        await update.message.reply_text(f"✅ Nome: {text}\nEnvie o ID do canal:")
        return True
    elif etapa == 'id':
        try:
            tid = int(text)
            if tid not in u['ids_canal']: u['ids_canal'].append(tid)
            success_text = f"✅ ID <code>{tid}</code> processado!\n\n"
            await mostrar_confirmacao_ids(update.message, context, extra_text=success_text)
        except: 
            await update.message.reply_text("❌ ID Inválido.")
        return True
    elif etapa == 'adicionando_horario':
        novos = [h.strip() for h in text.split(",") if h.strip() and validar_horario(h.strip())]
        if not novos:
            await update.message.reply_text("❌ Formato inválido (HH:MM).")
            return True
        atuais = u.get('horarios', [])
        for h in novos: 
            if h not in atuais: atuais.append(h)
        u['horarios'] = atuais
        u['etapa'] = 'horarios'
        success_text = f"✅ {len(novos)} horário(s) processado(s)!\n\n"
        await mostrar_painel_horarios(update.message, context, is_edicao=False, extra_text=success_text)
        return True
    return False
