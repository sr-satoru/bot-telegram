from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from modules.utils import is_super_admin

def get_main_keyboard(user_id: int):
    """Gera o teclado principal baseado no nível de acesso"""
    keyboard = [
        [InlineKeyboardButton("📢 Criar Canal", callback_data="criar_canal")],
        [InlineKeyboardButton("✏️ Editar Canal", callback_data="editar_canal")]
    ]
    if is_super_admin(user_id):
        keyboard.append([InlineKeyboardButton("👥 Gerenciar Admins", callback_data="gerenciar_admins")])
        keyboard.append([InlineKeyboardButton("📊 Painel de Controle", callback_data="painel_controle")])
    return keyboard

async def mostrar_menu_inicial_query(query, user_id: int):
    """Versão do menu inicial para CallbackQuery"""
    keyboard = get_main_keyboard(user_id)
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "🤖 <b>Bot de Postagens canais</b>\n\nEscolha uma opção:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def mostrar_menu_inicial_msg(message, user_id: int):
    """Versão do menu inicial para Message"""
    keyboard = get_main_keyboard(user_id)
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text(
        "🤖 <b>Bot de Postagens canais</b>\n\nEscolha uma opção:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def mostrar_menu_edicao(obj, context: ContextTypes.DEFAULT_TYPE, extra_text=""):
    """Mostra o menu principal de edição. obj pode ser Query ou Message."""
    dados = context.user_data.get('editando', {})
    
    if not dados:
        if hasattr(obj, 'edit_message_text'):
            await obj.edit_message_text("❌ Erro: dados de edição não encontrados.", parse_mode='HTML')
        else:
            await obj.reply_text("❌ Erro: dados de edição não encontrados.", parse_mode='HTML')
        return
    
    mensagem = extra_text or "🔧 <b>Menu de Edição</b>\n\n"
    if not extra_text:
        mensagem += f"📢 <b>Nome:</b> {dados['nome']}\n"
    else:
        # Se tem texto extra (ex: sucesso), o nome já está lá ou adicionamos info compacta
        mensagem += f"📢 Canal: <b>{dados['nome']}</b>\n"
        
    mensagem += f"🆔 <b>IDs:</b> {len(dados['ids'])} ID(s)\n"
    mensagem += f"🕒 <b>Horários:</b> {len(dados['horarios'])} horário(s)\n\n"
    mensagem += "Escolha o que deseja editar:"
    
    keyboard = [
        [
            InlineKeyboardButton("📛 Editar Nome", callback_data="edit_nome"),
        ],
        [
            InlineKeyboardButton("🆔 Gerenciar IDs", callback_data="edit_ids"),
        ],
        [
            InlineKeyboardButton("🕒 Gerenciar Horários", callback_data="edit_horarios_menu"),
        ],
        [
            InlineKeyboardButton("📝 Gerenciar Templates", callback_data="edit_templates"),
        ],
        [
            InlineKeyboardButton("🔘 Botões Globais", callback_data=f"global_button_tg_list_{dados.get('canal_id')}"),
        ],
        [
            InlineKeyboardButton("📸 Gerenciar Mídias", callback_data="edit_medias"),
        ],
        [
            InlineKeyboardButton("🗑️ Deletar Canal", callback_data="edit_deletar_canal"),
        ],
    ]
    
    if dados.get('changes_made', False):
        keyboard.append([
            InlineKeyboardButton("✅ Salvar Alterações", callback_data="edit_salvar"),
        ])
    
    keyboard.append([
        InlineKeyboardButton("⬅️ Voltar", callback_data="editar_canal"),
        InlineKeyboardButton("✖️ Cancelar", callback_data="edit_cancelar"),
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    from telegram import CallbackQuery
    
    if isinstance(obj, CallbackQuery):
        await obj.edit_message_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await obj.reply_text(mensagem, reply_markup=reply_markup, parse_mode='HTML')
