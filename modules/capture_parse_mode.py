import re
import html
from typing import List, Tuple, Optional, Dict
from telegram import Message, MessageEntity

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
    def convert_custom_emojis_to_html(message: Message) -> str:
        """
        Converte uma mensagem do Telegram em HTML, substituindo entidades por tags HTML.
        Garante aninhamento correto e evita duplicações através de segmentação por offsets.
        """
        if not message:
            return ""

        text = message.text or message.caption or ""
        entities = message.entities or message.caption_entities or []
        
        if not entities:
            return html.escape(text)

        # Pontos de interesse: offsets UTF-16 onde uma entidade começa ou termina
        text_utf16 = text.encode('utf-16-le')
        text_len_utf16 = len(text_utf16) // 2
        
        points = set([0, text_len_utf16])
        for ent in entities:
            points.add(ent.offset)
            points.add(ent.offset + ent.length)
        
        sorted_points = sorted([p for p in points if 0 <= p <= text_len_utf16])
        
        html_out = ""
        for i in range(len(sorted_points) - 1):
            start = sorted_points[i]
            end = sorted_points[i+1]
            if start == end:
                continue
            
            # Extrai o texto do segmento fielmente (UTF-16 safe)
            segment_text = text_utf16[start*2 : end*2].decode('utf-16-le')
            safe_text = html.escape(segment_text)
            
            # Entidades que cobrem este segmento específico
            # Filtramos as que cobrem TOTALMENTE o intervalo [start, end]
            segment_entities = [e for e in entities if e.offset <= start and (e.offset + e.length) >= end]
            
            # Ordena: entidades maiores (mais externas) primeiro
            segment_entities.sort(key=lambda x: x.length, reverse=True)
            
            tagged_segment = safe_text
            
            # Aplica as tags das entidades do segmento (de dentro para fora)
            # Para que a tag externa envolva as internas corretamente
            for ent in reversed(segment_entities):
                if ent.type == MessageEntity.CUSTOM_EMOJI:
                    tagged_segment = f'<tg-emoji emoji-id="{ent.custom_emoji_id}">{tagged_segment}</tg-emoji>'
                elif ent.type == MessageEntity.TEXT_LINK:
                    tagged_segment = f'<a href="{ent.url}">{tagged_segment}</a>'
                elif ent.type == MessageEntity.URL:
                    tagged_segment = f'<a href="{html.escape(segment_text)}">{tagged_segment}</a>'
                elif ent.type == MessageEntity.BOLD:
                    tagged_segment = f'<b>{tagged_segment}</b>'
                elif ent.type == MessageEntity.ITALIC:
                    tagged_segment = f'<i>{tagged_segment}</i>'
                elif ent.type == MessageEntity.UNDERLINE:
                    tagged_segment = f'<u>{tagged_segment}</u>'
                elif ent.type == MessageEntity.STRIKETHROUGH:
                    tagged_segment = f'<s>{tagged_segment}</s>'
                elif ent.type == MessageEntity.CODE:
                    tagged_segment = f'<code>{tagged_segment}</code>'
                elif ent.type == MessageEntity.PRE:
                    tagged_segment = f'<pre>{tagged_segment}</pre>'
            
            html_out += tagged_segment
            
        return html_out
    
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

