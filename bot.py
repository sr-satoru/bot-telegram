import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
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
   
2. O bot irá salvar o template e você precisará fornecer os links URL na ordem

3. Use /listar para ver todos os templates salvos
4. Use /enviar <id> para enviar um template formatado

Comandos disponíveis:
/start - Mostra esta mensagem
/listar - Lista todos os templates
/enviar <id> - Envia um template (você precisará fornecer o link)
/help - Mostra ajuda
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
        
        response += f"\nEnvie o URL do primeiro link (1/{num_links}):\n"
        response += "Exemplo: https://example.com"
        
        await update.message.reply_text(response)
    else:
        # Verifica se há um template pendente esperando pelos links
        if 'pending_template' in context.user_data:
            # Assume que esta mensagem é um link URL
            link_url = message_text.strip()
            
            # Valida se parece ser uma URL
            if not (link_url.startswith('http://') or link_url.startswith('https://')):
                await update.message.reply_text(
                    "⚠️ Por favor, envie uma URL válida começando com http:// ou https://"
                )
                return
            
            # Adiciona o link à lista
            template_data = context.user_data['pending_template']
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
        else:
            # Mensagem normal sem template
            await update.message.reply_text(
                "💬 Para salvar um template, use o formato:\n"
                "{link = palavra ou frase}\n\n"
                "Exemplo: Olá {link = clique aqui} tudo certo {link = me responde}"
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
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Inicia o bot
    logger.info("Bot iniciado!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

