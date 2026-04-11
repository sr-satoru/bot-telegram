import logging
from telegram import Message
from modules.capture_parse_mode import MessageParser
from db_helpers import save_template

logger = logging.getLogger(__name__)

async def processar_e_salvar_template_da_legenda(message: Message, canal_id: int) -> int:
    """
    Extrai o template da legenda de uma mensagem, preservando formatação e emojis premium,
    e o salva no banco de dados vinculado ao canal.
    
    Retorna o ID do template criado ou None se não houver legenda.
    """
    if not message.caption:
        return None
        
    try:
        parser = MessageParser()
        
        # 1. Converte a legenda em HTML (suporta emojis premium, negrito, etc)
        html_text = parser.convert_custom_emojis_to_html(message)
        
        # 2. Parseia o HTML para o formato de template (extrai links para placeholders [[link_N]])
        template_data = parser.parse_and_save_template(html_text)
        
        if not template_data:
            logger.warning(f"Falha ao parsear template da legenda: {message.caption[:50]}...")
            return None
            
        # 3. Salva o template no banco
        # template_data tem: 'template_mensagem', 'segmentos', 'urls_originais'
        links = list(zip(template_data['segmentos'], template_data['urls_originais']))
        
        template_id = await save_template(
            canal_id=canal_id,
            template_mensagem=template_data['template_mensagem'],
            links=links
        )
        
        logger.info(f"Template automático criado com sucesso (ID: {template_id}) para o canal {canal_id}")
        return template_id
        
    except Exception as e:
        logger.error(f"Erro ao processar template automático da legenda: {e}", exc_info=True)
        return None
