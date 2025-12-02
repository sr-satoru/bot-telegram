import re
from typing import List, Tuple, Optional

class MessageParser:
    """Parser para extrair variáveis {link = ...} das mensagens"""
    
    @staticmethod
    def extract_link_variables(text: str) -> List[Tuple[str, str]]:
        """
        Extrai variáveis de link do formato {link = texto}
        Retorna uma lista de tuplas: [(texto_com_link, texto_original), ...]
        """
        pattern = r'\{link\s*=\s*([^}]+)\}'
        matches = re.finditer(pattern, text)
        
        results = []
        for match in matches:
            link_text = match.group(1).strip()
            results.append((link_text, match.group(0)))
        
        return results
    
    @staticmethod
    def parse_and_save_template(text: str) -> Optional[dict]:
        """
        Parseia uma mensagem e retorna um dicionário com as informações do template
        Suporta múltiplos links na mesma mensagem
        Retorna None se não houver variáveis de link
        """
        link_vars = MessageParser.extract_link_variables(text)
        
        if not link_vars:
            return None
        
        # Remove todas as variáveis do texto original para obter o template
        template_mensagem = text
        segmentos = []
        link_vars_original = []
        
        for link_text, link_var in link_vars:
            template_mensagem = template_mensagem.replace(link_var, link_text)
            segmentos.append(link_text)
            link_vars_original.append(link_var)
        
        return {
            'template_mensagem': template_mensagem,
            'segmentos': segmentos,
            'link_vars': link_vars_original,
            'num_links': len(segmentos)
        }
    
    @staticmethod
    def format_message_with_links(template_mensagem: str, links: List[Tuple[str, str]]) -> str:
        """
        Formata uma mensagem HTML com múltiplos links embutidos
        links: Lista de tuplas (segmento_com_link, link_url) na ordem de aparição
        Suporta segmentos repetidos, aplicando cada link na ordem correta
        """
        # Escapa caracteres HTML especiais no template
        formatted = template_mensagem.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Usa um offset para rastrear mudanças no tamanho do texto após substituições
        # Isso garante que mesmo segmentos repetidos sejam substituídos na ordem correta
        offset = 0
        
        # Aplica os links na ordem de aparição (da esquerda para direita)
        for segmento, link_url in links:
            # Escapa o URL
            link_url_escaped = link_url.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            
            # Encontra a próxima ocorrência do segmento no texto
            # Começa a busca após o offset (última posição substituída)
            pattern = re.escape(segmento)
            
            # Busca a partir do offset atual
            search_text = formatted[offset:]
            match = re.search(pattern, search_text)
            
            if match:
                # Ajusta a posição considerando o offset
                start = offset + match.start()
                end = offset + match.end()
                
                # Substitui esta ocorrência específica
                link_html = f'<a href="{link_url_escaped}">{segmento}</a>'
                formatted = formatted[:start] + link_html + formatted[end:]
                
                # Atualiza o offset para a posição após a substituição
                # Isso garante que a próxima busca não encontre esta ocorrência novamente
                offset = start + len(link_html)
            else:
                # Se não encontrou, tenta encontrar em todo o texto (fallback)
                # Isso pode acontecer se houver algum problema com o offset
                match = re.search(pattern, formatted)
                if match:
                    start, end = match.span()
                    link_html = f'<a href="{link_url_escaped}">{segmento}</a>'
                    formatted = formatted[:start] + link_html + formatted[end:]
                    offset = start + len(link_html)
        
        return formatted

