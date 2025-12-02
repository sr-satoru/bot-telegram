import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from database import Database
from parser import MessageParser

# Carrega variáveis de ambiente
load_dotenv()

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Inicializa banco de dados e parser
db = Database()
parser = MessageParser()

# Token do bot (deve estar no arquivo .env)
BOT_TOKEN = os.getenv('BOT_TOKEN')

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN não encontrado no arquivo .env")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para o comando /start"""
    welcome_message = """
🤖 Bot de Templates com Links

Este bot permite salvar mensagens com templates que contêm links.

📝 Como usar:
1. Envie uma mensagem com o formato: {link = palavra ou frase}
   Exemplo: "Olá {link = clique aqui} tudo certo {link = me responde"
   
2. Se houver múltiplos links, você pode escolher:
   • Usar o mesmo link para todos os segmentos
   • Usar links diferentes para cada segmento

3. Use /enviar <id> para enviar um template formatado
4. Use /editar <id> para editar os links dos segmentos de um template

Comandos disponíveis:
/start - Mostra esta mensagem
/enviar <id> - Envia um template formatado
/editar <id> - Edita os links dos segmentos de um template
"""
    await update.message.reply_text(welcome_message)



async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para mensagens de texto"""
    message_text = update.message.text
    
    # Verifica se a mensagem contém variável de link
    parsed = parser.parse_and_save_template(message_text)
    
    if parsed:
        # Salva o template temporariamente no contexto do usuário
        # O usuário precisará fornecer os links depois
        context.user_data['pending_template'] = parsed
        context.user_data['original_message'] = message_text
        context.user_data['links_received'] = []
        context.user_data['current_link_index'] = 0
        
        num_links = parsed['num_links']
        segmentos = parsed['segmentos']
        
        response = f"""
✅ Template detectado com {num_links} link(s)!

📝 Template: {parsed['template_mensagem']}

"""
        for i, segmento in enumerate(segmentos, 1):
            response += f"🔗 Link {i}: segmento '{segmento}'\n"
        
        # Se houver múltiplos links, mostra botões inline para escolher
        if num_links > 1:
            response += f"\n📌 Como deseja configurar os links?"
            context.user_data['waiting_for_link_choice'] = True
            
            # Cria botões inline
            keyboard = [
                [
                    InlineKeyboardButton("🔗 Mesmo link para todos", callback_data="link_choice_same"),
                ],
                [
                    InlineKeyboardButton("🔗 Links separados", callback_data="link_choice_separate"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(response, reply_markup=reply_markup)
        else:
            # Se for apenas 1 link, vai direto pedir o URL
            response += f"\nEnvie o URL do link:\n"
            response += "Exemplo: https://example.com"
            context.user_data['waiting_for_link_choice'] = False
            await update.message.reply_text(response)
    else:
        # Verifica se está editando todos os links
        if context.user_data.get('editing_all_links', False):
            link_url = message_text.strip()
            
            # Valida se parece ser uma URL
            if not (link_url.startswith('http://') or link_url.startswith('https://')):
                await update.message.reply_text(
                    "⚠️ Por favor, envie uma URL válida começando com http:// ou https://"
                )
                return
            
            template_id = context.user_data['editing_template_id']
            num_links = context.user_data['editing_num_links']
            
            # Atualiza todos os links
            updated_count = db.update_all_links(template_id, link_url)
            
            if updated_count > 0:
                # Limpa o contexto de edição
                del context.user_data['editing_all_links']
                del context.user_data['editing_template_id']
                del context.user_data['editing_num_links']
                
                # Retorna ao painel de edição com mensagem de sucesso
                url_display = link_url if len(link_url) <= 50 else link_url[:47] + "..."
                success_msg = f"Todos os {updated_count} segmentos atualizados para: {url_display}"
                await show_edit_panel(update, template_id, success_msg)
            else:
                await update.message.reply_text(
                    "❌ Erro ao atualizar os links. Por favor, tente novamente."
                )
            return
        
        # Verifica se está editando um link
        if 'editing_link_id' in context.user_data:
            link_url = message_text.strip()
            
            # Valida se parece ser uma URL
            if not (link_url.startswith('http://') or link_url.startswith('https://')):
                await update.message.reply_text(
                    "⚠️ Por favor, envie uma URL válida começando com http:// ou https://"
                )
                return
            
            # Atualiza o link
            link_id = context.user_data['editing_link_id']
            template_id = context.user_data['editing_template_id']
            segmento = context.user_data['editing_segmento']
            ordem = context.user_data['editing_ordem']
            
            updated = db.update_link(link_id, link_url)
            
            if updated:
                # Limpa o contexto de edição
                del context.user_data['editing_link_id']
                del context.user_data['editing_template_id']
                del context.user_data['editing_segmento']
                del context.user_data['editing_ordem']
                
                # Retorna ao painel de edição com mensagem de sucesso
                url_display = link_url if len(link_url) <= 50 else link_url[:47] + "..."
                success_msg = f"Segmento {ordem} ('{segmento}') atualizado: {url_display}"
                await show_edit_panel(update, template_id, success_msg)
            else:
                await update.message.reply_text(
                    "❌ Erro ao atualizar o link. Por favor, tente novamente."
                )
                # Mantém o contexto para tentar novamente
            return
        
        # Verifica se há um template pendente esperando pelos links
        if 'pending_template' in context.user_data:
            template_data = context.user_data['pending_template']
            num_links = template_data['num_links']
            
            # Assume que esta mensagem é um link URL
            link_url = message_text.strip()
            
            # Valida se parece ser uma URL
            if not (link_url.startswith('http://') or link_url.startswith('https://')):
                await update.message.reply_text(
                    "⚠️ Por favor, envie uma URL válida começando com http:// ou https://"
                )
                return
            
            # Verifica se está usando o mesmo link para todos
            if context.user_data.get('use_same_link', False):
                # Aplica o mesmo link para todos os segmentos
                segmentos = template_data['segmentos']
                links_list = [(seg, link_url) for seg in segmentos]
                
                # Salva o template
                template_id = db.save_template(
                    template_mensagem=template_data['template_mensagem'],
                    links=links_list
                )
                
                await update.message.reply_text(
                    f"✅ Template salvo com sucesso!\n"
                    f"ID: {template_id}\n"
                    f"Total de links: {num_links} (mesmo URL para todos)\n"
                    f"URL: {link_url}\n"
                    f"Use /enviar {template_id} para enviar esta mensagem formatada."
                )
                
                # Limpa o template pendente
                del context.user_data['pending_template']
                del context.user_data['original_message']
                del context.user_data['links_received']
                del context.user_data['current_link_index']
                del context.user_data['use_same_link']
                del context.user_data['waiting_for_link_choice']
                return
            
            # Adiciona o link à lista (modo separado)
            current_index = context.user_data['current_link_index']
            segmentos = template_data['segmentos']
            
            # Valida se o índice está dentro do range
            if current_index >= len(segmentos):
                await update.message.reply_text(
                    "⚠️ Erro: índice de segmento inválido. Por favor, tente novamente."
                )
                # Limpa o estado
                del context.user_data['pending_template']
                del context.user_data['original_message']
                del context.user_data['links_received']
                del context.user_data['current_link_index']
                if 'use_same_link' in context.user_data:
                    del context.user_data['use_same_link']
                if 'waiting_for_link_choice' in context.user_data:
                    del context.user_data['waiting_for_link_choice']
                return
            
            context.user_data['links_received'].append((segmentos[current_index], link_url))
            context.user_data['current_link_index'] += 1
            
            num_links = template_data['num_links']
            links_received = len(context.user_data['links_received'])
            
            # Verifica se ainda faltam links
            if links_received < num_links:
                # Pede o próximo link (current_index já foi incrementado)
                next_index = context.user_data['current_link_index']
                if next_index < len(segmentos):
                    next_segmento = segmentos[next_index]
                    await update.message.reply_text(
                        f"✅ Link {links_received}/{num_links} recebido!\n\n"
                        f"Agora envie o URL para o segmento '{next_segmento}' ({links_received + 1}/{num_links}):"
                    )
                else:
                    await update.message.reply_text(
                        f"⚠️ Erro: não há mais segmentos disponíveis. Por favor, tente novamente."
                    )
            else:
                # Todos os links foram recebidos, salva o template
                template_id = db.save_template(
                    template_mensagem=template_data['template_mensagem'],
                    links=context.user_data['links_received']
                )
                
                await update.message.reply_text(
                    f"✅ Template salvo com sucesso!\n"
                    f"ID: {template_id}\n"
                    f"Total de links: {num_links}\n"
                    f"Use /enviar {template_id} para enviar esta mensagem formatada."
                )
                
                # Limpa o template pendente
                del context.user_data['pending_template']
                del context.user_data['original_message']
                del context.user_data['links_received']
                del context.user_data['current_link_index']
                if 'use_same_link' in context.user_data:
                    del context.user_data['use_same_link']
                if 'waiting_for_link_choice' in context.user_data:
                    del context.user_data['waiting_for_link_choice']
        else:
            # Mensagem normal sem template
            await update.message.reply_text(
                "💬 Para salvar um template, use o formato:\n"
                "{link = palavra ou frase}\n\n"
                "Exemplo: Olá {link = clique aqui} tudo certo {link = me responde}"
            )
            
async def handle_link_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para processar a escolha de tipo de link via botões inline"""
    query = update.callback_query
    await query.answer()
    
    # Verifica se há um template pendente
    if 'pending_template' not in context.user_data:
        await query.edit_message_text("⚠️ Template não encontrado. Por favor, envie um novo template.")
        return
    
    template_data = context.user_data['pending_template']
    num_links = template_data['num_links']
    segmentos = template_data['segmentos']
    
    if query.data == "link_choice_same":
        # Usar o mesmo link para todos
        context.user_data['use_same_link'] = True
        context.user_data['waiting_for_link_choice'] = False
        
        await query.edit_message_text(
            f"✅ Você escolheu usar o mesmo link para todos os {num_links} segmentos.\n\n"
            f"Envie o URL do link:\n"
            f"Exemplo: https://example.com"
        )
    elif query.data == "link_choice_separate":
        # Usar links separados
        context.user_data['use_same_link'] = False
        context.user_data['waiting_for_link_choice'] = False
        
        await query.edit_message_text(
            f"✅ Você escolheu usar links separados.\n\n"
            f"Envie o URL do primeiro link (1/{num_links}):\n"
            f"Segmento: '{segmentos[0]}'\n"
            f"Exemplo: https://example.com"
        )

async def show_edit_panel(update_or_query, template_id: int, success_message: str = None):
    """
    Função auxiliar para mostrar o painel de edição
    Pode receber Update ou CallbackQuery
    """
    template = db.get_template_with_link_ids(template_id)
    
    if not template:
        if hasattr(update_or_query, 'edit_message_text'):
            await update_or_query.edit_message_text(f"❌ Template com ID {template_id} não encontrado.")
        else:
            await update_or_query.message.reply_text(f"❌ Template com ID {template_id} não encontrado.")
        return
    
    template_mensagem = template['template_mensagem']
    links = template['links']  # [(link_id, segmento, url, ordem), ...]
    
    # Monta a mensagem com os segmentos
    message_text = f"📝 Template ID: {template_id}\n\n"
    message_text += f"📄 Mensagem:\n{template_mensagem}\n\n"
    
    if success_message:
        message_text += f"✅ {success_message}\n\n"
    
    message_text += f"🔗 Segmentos ({len(links)}):\n\n"
    
    # Cria botões inline para cada segmento
    keyboard = []
    for link_id, segmento, url, ordem in links:
        # Trunca URL se muito longo para exibição
        url_display = url if len(url) <= 40 else url[:37] + "..."
        message_text += f"{ordem}. '{segmento}'\n   → {url_display}\n\n"
        
        # Botão para editar este segmento
        segmento_display = segmento[:20] + "..." if len(segmento) > 20 else segmento
        keyboard.append([
            InlineKeyboardButton(
                f"✏️ Editar segmento {ordem}: {segmento_display}",
                callback_data=f"edit_link_{link_id}"
            )
        ])
    
    # Botão para editar todos os links de uma vez
    if len(links) > 1:
        keyboard.append([
            InlineKeyboardButton("🔗 Editar todos para o mesmo link", callback_data=f"edit_all_{template_id}")
        ])
    
    # Botão para cancelar
    keyboard.append([
        InlineKeyboardButton("❌ Cancelar", callback_data="edit_cancel")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Envia ou edita a mensagem dependendo do tipo
    if hasattr(update_or_query, 'edit_message_text'):
        await update_or_query.edit_message_text(
            message_text,
            reply_markup=reply_markup
        )
    else:
        await update_or_query.message.reply_text(
            message_text,
            reply_markup=reply_markup
        )

async def edit_segment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para o comando /editar"""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Use: /editar <id>\n"
            "Exemplo: /editar 1\n\n"
            "Este comando permite editar os links dos segmentos de uma mensagem."
        )
        return
    
    try:
        template_id = int(context.args[0])
        await show_edit_panel(update, template_id)
        
    except ValueError:
        await update.message.reply_text("⚠️ ID deve ser um número.")
    except Exception as e:
        logger.error(f"Erro ao editar template: {e}")
        await update.message.reply_text(f"❌ Erro ao editar template: {str(e)}")

async def handle_edit_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para processar a edição de links via botões inline"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "edit_cancel":
        await query.edit_message_text("❌ Edição cancelada.")
        return
    
    if query.data.startswith("edit_all_"):
        template_id = int(query.data.split("_")[-1])
        
        # Busca informações do template
        template = db.get_template_with_link_ids(template_id)
        
        if not template:
            await query.edit_message_text("❌ Template não encontrado.")
            return
        
        num_links = len(template['links'])
        
        # Salva o contexto para edição de todos
        context.user_data['editing_all_links'] = True
        context.user_data['editing_template_id'] = template_id
        context.user_data['editing_num_links'] = num_links
        
        await query.edit_message_text(
            f"🔗 Editando todos os links\n\n"
            f"📝 Template ID: {template_id}\n"
            f"🔗 Total de segmentos: {num_links}\n\n"
            f"Envie o URL que será aplicado a TODOS os segmentos:\n"
            f"Exemplo: https://example.com"
        )
        return
    
    if query.data.startswith("edit_link_"):
        link_id = int(query.data.split("_")[-1])
        
        # Busca informações do link
        link_info = db.get_link_info(link_id)
        
        if not link_info:
            await query.edit_message_text("❌ Link não encontrado.")
            return
        
        link_id_db, template_id, segmento, url_atual, ordem = link_info
        
        # Salva o contexto para edição
        context.user_data['editing_link_id'] = link_id
        context.user_data['editing_template_id'] = template_id
        context.user_data['editing_segmento'] = segmento
        context.user_data['editing_ordem'] = ordem
        
        await query.edit_message_text(
            f"✏️ Editando segmento {ordem}\n\n"
            f"📝 Segmento: '{segmento}'\n"
            f"🔗 URL atual: {url_atual}\n\n"
            f"Envie o novo URL para este segmento:\n"
            f"Exemplo: https://example.com"
        )

async def send_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para o comando /enviar"""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Use: /enviar <id>\n"
            "Exemplo: /enviar 1"
        )
        return
    
    try:
        template_id = int(context.args[0])
        template = db.get_template(template_id)
        
        if not template:
            await update.message.reply_text(f"❌ Template com ID {template_id} não encontrado.")
            return
        
        template_mensagem = template['template_mensagem']
        links = template['links']
        
        # Formata a mensagem com todos os links HTML
        formatted_message = parser.format_message_with_links(
            template_mensagem,
            links
        )
        
        # Envia a mensagem formatada
        await update.message.reply_text(
            formatted_message,
            parse_mode='HTML'
        )   
    except Exception as e:
        logger.error(f"Erro ao enviar template: {e}")

def main():
    """Função principal para iniciar o bot"""
    # Cria a aplicação
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Adiciona handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("enviar", send_template))
    application.add_handler(CommandHandler("editar", edit_segment))
    application.add_handler(CallbackQueryHandler(handle_link_choice, pattern="^link_choice_"))
    application.add_handler(CallbackQueryHandler(handle_edit_link, pattern="^edit_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Inicia o bot
    logger.info("Bot iniciado!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

