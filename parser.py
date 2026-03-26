import re
from typing import List, Tuple, Optional, Dict

class MessageParser:
    """Parser para extrair links de mensagens HTML e formatar templates preservando tags do Telegram"""
    
    @staticmethod
    def parse_and_save_template(html_text: str) -> Optional[Dict]:
        """
        Parseia uma mensagem HTML e retorna informações do template.
        Identifica automaticamente tags <a> e as substitui por placeholders [[link_N]].
        Retorna None se não houver links (pode ser usado como template estático).
        """
        # Regex para capturar tags <a>: grupo 1 = URL, grupo 2 = Conteúdo (inclui outras tags)
        pattern = r'<a href="([^"]+)">([\s\S]*?)</a>'
        matches = list(re.finditer(pattern, html_text))
        
        if not matches:
            # Retorna o próprio HTML como template se não houver links
            return {
                'template_mensagem': html_text,
                'segmentos': [],
                'link_vars': [], # Antigo links_originais, mantido por compatibilidade
                'urls_originais': [],
                'num_links': 0
            }
        
        template_mensagem = html_text
        segmentos = []
        urls_originais = []
        
        # Faz as substituições de trás para frente para não bagunçar os índices
        for i, match in enumerate(reversed(matches)):
            idx = len(matches) - i
            url = match.group(1)
            content = match.group(2)
            
            placeholder = f"[[link_{idx}]]"
            start, end = match.span()
            
            template_mensagem = template_mensagem[:start] + placeholder + template_mensagem[end:]
            
            # Adiciona na ordem correta no final (invertendo a reversão)
            segmentos.insert(0, content)
            urls_originais.insert(0, url)
            
        return {
            'template_mensagem': template_mensagem,
            'segmentos': segmentos,
            'urls_originais': urls_originais,
            'num_links': len(segmentos)
        }
    
    @staticmethod
    def format_message_with_links(template_html: str, links: List[Tuple[str, str]]) -> str:
        """
        Reconstrói a mensagem HTML substituindo placeholders [[link_N]] pelos URLs atuais.
        links: Lista de tuplas (segmento_com_tags, link_url)
        """
        formatted = template_html
        
        # Substitui [[link_N]] baseado na ordem fornecida
        for i, (segmento, link_url) in enumerate(links, 1):
            placeholder = f"[[link_{i}]]"
            # O link_url já deve estar devidamente escapado se vier do banco/user
            link_html = f'<a href="{link_url}">{segmento}</a>'
            formatted = formatted.replace(placeholder, link_html)
            
        return formatted

