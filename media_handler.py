"""
Módulo para gerenciamento de mídias e grupos de mídias do bot
Permite armazenar mídias usando file_id do Telegram (sem salvar arquivos no servidor)
"""

import logging
from typing import Optional, List, Dict, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes
from database import Database

logger = logging.getLogger(__name__)

class MediaHandler:
    """Classe para gerenciar mídias e grupos de mídias"""
    
    def __init__(self, database: Database):
        self.db = database
    
    def extract_media_info(self, update: Update) -> Optional[Dict]:
        """
        Extrai informações de mídia de uma mensagem
        Retorna dict com file_id, tipo, etc. ou None se não houver mídia
        """
        message = update.message
        
        if message.photo:
            # Foto - pega a maior resolução
            photo = message.photo[-1]
            return {
                'file_id': photo.file_id,
                'file_unique_id': photo.file_unique_id,
                'media_type': 'photo',
                'file_size': photo.file_size,
                'width': photo.width,
                'height': photo.height,
                'duration': None,
                'thumbnail_file_id': None
            }
        
        elif message.video:
            video = message.video
            return {
                'file_id': video.file_id,
                'file_unique_id': video.file_unique_id,
                'media_type': 'video',
                'file_size': video.file_size,
                'width': video.width,
                'height': video.height,
                'duration': video.duration,
                'thumbnail_file_id': video.thumbnail.file_id if video.thumbnail else None
            }
        
        elif message.document:
            doc = message.document
            # Verifica se é uma imagem ou vídeo
            if doc.mime_type:
                if doc.mime_type.startswith('image/'):
                    return {
                        'file_id': doc.file_id,
                        'file_unique_id': doc.file_unique_id,
                        'media_type': 'photo',
                        'file_size': doc.file_size,
                        'width': None,
                        'height': None,
                        'duration': None,
                        'thumbnail_file_id': None
                    }
                elif doc.mime_type.startswith('video/'):
                    return {
                        'file_id': doc.file_id,
                        'file_unique_id': doc.file_unique_id,
                        'media_type': 'video',
                        'file_size': doc.file_size,
                        'width': None,
                        'height': None,
                        'duration': None,
                        'thumbnail_file_id': None
                    }
        
        return None
    
    def save_media_from_message(self, update: Update) -> Optional[int]:
        """
        Salva uma mídia recebida em uma mensagem
        Retorna o ID da mídia salva ou None
        """
        media_info = self.extract_media_info(update)
        
        if not media_info:
            return None
        
        media_id = self.db.save_media(
            file_id=media_info['file_id'],
            file_unique_id=media_info['file_unique_id'],
            media_type=media_info['media_type'],
            file_size=media_info['file_size'],
            width=media_info['width'],
            height=media_info['height'],
            duration=media_info['duration'],
            thumbnail_file_id=media_info['thumbnail_file_id']
        )
        
        return media_id
    
    async def send_media_group(self, context: Optional[ContextTypes.DEFAULT_TYPE] = None,
                               chat_id: str = None, media_group: Dict = None,
                               caption: Optional[str] = None,
                               parse_mode: str = 'HTML',
                               reply_markup: Optional[InlineKeyboardMarkup] = None,
                               bot = None) -> bool:
        """
        Envia um grupo de mídias para um chat
        Pode usar context.bot ou bot diretamente
        """
        try:
            # Determina qual bot usar
            if bot:
                bot_instance = bot
            elif context:
                bot_instance = context.bot
            else:
                logger.error("Erro: precisa fornecer context ou bot")
                return False
            
            medias = media_group.get('medias', [])
            
            if not medias:
                logger.warning(f"Tentativa de enviar grupo de mídias vazio: {media_group.get('id')}")
                return False
            
            # Prepara lista de InputMedia para o media group
            input_medias = []
            
            for i, media in enumerate(medias):
                media_caption = None
                
                # A caption só pode ir na primeira mídia
                if i == 0:
                    media_caption = caption
                
                if media['media_type'] == 'photo':
                    input_medias.append(
                        InputMediaPhoto(
                            media=media['file_id'],
                            caption=media_caption,
                            parse_mode=parse_mode if i == 0 else None
                        )
                    )
                elif media['media_type'] == 'video':
                    input_medias.append(
                        InputMediaVideo(
                            media=media['file_id'],
                            caption=media_caption,
                            parse_mode=parse_mode if i == 0 else None
                        )
                    )
            
            # Envia o media group
            sent_messages = await bot_instance.send_media_group(
                chat_id=chat_id,
                media=input_medias
            )
            
            # Se houver botões, edita a primeira mensagem para adicionar
            if reply_markup and sent_messages:
                try:
                    # Se tem caption, edita caption e botões juntos
                    if caption:
                        await sent_messages[0].edit_caption(
                            caption=caption,
                            reply_markup=reply_markup,
                            parse_mode=parse_mode
                        )
                        logger.info(f"Botões inline e caption adicionados ao media group {media_group.get('id')}")
                    else:
                        # Se não tem caption, tenta apenas adicionar botões
                        await sent_messages[0].edit_reply_markup(reply_markup=reply_markup)
                        logger.info(f"Botões inline adicionados ao media group {media_group.get('id')} (sem caption)")
                except Exception as e:
                    logger.error(f"Erro ao adicionar botões inline ao media group {media_group.get('id')}: {e}")
                    # Tenta novamente com edit_caption mesmo sem caption
                    try:
                        await sent_messages[0].edit_caption(
                            caption=caption if caption else "",
                            reply_markup=reply_markup,
                            parse_mode=parse_mode if caption else None
                        )
                        logger.info(f"Botões inline adicionados via edit_caption ao media group {media_group.get('id')}")
                    except Exception as e2:
                        logger.error(f"Erro ao editar caption com botões: {e2}")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao enviar media group: {e}")
            return False
    
    async def send_single_media(self, context: ContextTypes.DEFAULT_TYPE,
                                chat_id: str, media: Dict,
                                caption: Optional[str] = None,
                                parse_mode: str = 'HTML',
                                reply_markup: Optional[InlineKeyboardMarkup] = None) -> bool:
        """
        Envia uma única mídia para um chat
        """
        try:
            if media['media_type'] == 'photo':
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=media['file_id'],
                    caption=caption,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
            elif media['media_type'] == 'video':
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=media['file_id'],
                    caption=caption,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup
                )
            else:
                logger.warning(f"Tipo de mídia não suportado: {media['media_type']}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao enviar mídia: {e}")
            return False
    
    def format_media_group_list(self, groups: List[Dict]) -> str:
        """
        Formata lista de grupos de mídias para exibição
        """
        if not groups:
            return "❌ Nenhum grupo de mídias encontrado."
        
        message = "📦 <b>Grupos de Mídias</b>\n\n"
        
        for group in groups:
            media_count = group.get('media_count', 0)
            nome = group['nome']
            group_id = group['id']
            
            message += f"📦 <b>{nome}</b>\n"
            message += f"   • ID: {group_id}\n"
            message += f"   • Mídias: {media_count}\n\n"
        
        return message
    
    def create_media_group_keyboard(self, groups: List[Dict], 
                                    prefix: str = "select_media_group",
                                    show_back: bool = True,
                                    back_callback: str = "voltar_start") -> InlineKeyboardMarkup:
        """
        Cria teclado inline para listar grupos de mídias
        """
        keyboard = []
        
        for group in groups:
            nome = group['nome']
            group_id = group['id']
            media_count = group.get('media_count', 0)
            
            display_name = f"📦 {nome} ({media_count})"
            if len(display_name) > 40:
                display_name = display_name[:37] + "..."
            
            keyboard.append([
                InlineKeyboardButton(
                    display_name,
                    callback_data=f"{prefix}_{group_id}"
                )
            ])
        
        if show_back:
            keyboard.append([
                InlineKeyboardButton("⬅️ Voltar", callback_data=back_callback)
            ])
        
        return InlineKeyboardMarkup(keyboard)
    
    def get_auto_template(self, media_group: Dict, database: Database) -> Optional[Dict]:
        """
        Busca template automático para um grupo de mídias
        Se o grupo não tiver template associado, busca qualquer template do canal
        """
        # Se já tem template associado, retorna None (não precisa buscar)
        if media_group.get('template_id'):
            return None
        
        # Se não tem canal_id, não pode buscar template automático
        if not media_group.get('canal_id'):
            return None
        
        # Busca templates do canal
        templates = database.get_templates_by_canal(media_group['canal_id'])
        if templates:
            # Retorna o primeiro template disponível
            return database.get_template(templates[0]['id'])
        
        return None
    
    async def send_media_group_with_template(self, context: Optional[ContextTypes.DEFAULT_TYPE] = None,
                                            chat_id: str = None, media_group: Dict = None,
                                            template: Optional[Dict] = None,
                                            global_buttons: Optional[List[Dict]] = None,
                                            database: Optional[Database] = None,
                                            use_auto_template: bool = True,
                                            bot = None) -> bool:
        """
        Envia um grupo de mídias com template e botões aplicados
        use_auto_template: Se True e não houver template, busca automaticamente do canal
        """
        # Se não tem template e use_auto_template está ativo, busca template automático
        if not template and use_auto_template and database:
            auto_template = self.get_auto_template(media_group, database)
            if auto_template:
                template = auto_template
        
        # Se não tem global_buttons mas tem canal_id, busca botões globais automaticamente
        if not global_buttons and database and media_group.get('canal_id'):
            global_buttons = database.get_global_buttons(media_group['canal_id'])
            if not global_buttons:
                global_buttons = None
        
        # Prepara caption do template
        caption = None
        reply_markup = None
        
        # Prepara botões (mesmo sem template, se houver botões globais)
        all_buttons = []
        
        if template:
            # Formata mensagem do template com links
            from parser import MessageParser
            parser = MessageParser()
            
            template_text = template['template_mensagem']
            links = template.get('links', [])
            
            # Aplica links ao template
            # links pode ser lista de dicts ou lista de tuplas (link_id, segmento, url, ordem)
            if links:
                if isinstance(links[0], dict):
                    # Formato: [{'segmento': ..., 'link': ...}, ...]
                    link_tuples = [(link.get('segmento', ''), link.get('link', '')) for link in links]
                else:
                    # Formato: [(link_id, segmento, url, ordem), ...]
                    link_tuples = [(link[1], link[2]) for link in links]
                
                caption = parser.format_message_with_links(template_text, link_tuples)
            else:
                caption = template_text
            
            # Adiciona botões do template
            inline_buttons = template.get('inline_buttons', [])
            for button in inline_buttons:
                all_buttons.append(InlineKeyboardButton(button['text'], url=button['url']))
        
        # Adiciona botões globais se houver (mesmo sem template)
        if global_buttons:
            for button in global_buttons:
                all_buttons.append(InlineKeyboardButton(button['text'], url=button['url']))
        
        # Organiza botões: se houver 2 ou mais, um abaixo do outro (um por linha)
        if all_buttons:
            if len(all_buttons) >= 2:
                # Quando há 2 ou mais botões, cada um fica em sua própria linha
                button_rows = [[button] for button in all_buttons]
            else:
                # Se houver apenas 1 botão, mantém como está
                button_rows = [all_buttons]
            reply_markup = InlineKeyboardMarkup(button_rows)
            logger.info(f"Preparando {len(all_buttons)} botões inline para media group {media_group.get('id')}")
        else:
            logger.info(f"Nenhum botão inline para media group {media_group.get('id')}")
        
        # Envia o media group
        return await self.send_media_group(
            context=context,
            chat_id=chat_id,
            media_group=media_group,
            caption=caption,
            reply_markup=reply_markup,
            bot=bot
        )

