"""
Módulo para gerenciamento de mídias e grupos de mídias do bot
Permite armazenar mídias usando file_id do Telegram (sem salvar arquivos no servidor)
"""

import logging
from typing import Optional, List, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import ContextTypes
from db import prisma

logger = logging.getLogger(__name__)


class MediaHandler:
    """Classe para gerenciar mídias e grupos de mídias"""

    def extract_media_info(self, update: Update) -> Optional[Dict]:
        """
        Extrai informações de mídia de uma mensagem
        Retorna dict com file_id, tipo, etc. ou None se não houver mídia
        """
        message = update.message

        if message.photo:
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
            if doc.mime_type:
                if doc.mime_type.startswith('image/'):
                    return {
                        'file_id': doc.file_id,
                        'file_unique_id': doc.file_unique_id,
                        'media_type': 'photo',
                        'file_size': doc.file_size,
                        'width': None, 'height': None,
                        'duration': None, 'thumbnail_file_id': None
                    }
                elif doc.mime_type.startswith('video/'):
                    return {
                        'file_id': doc.file_id,
                        'file_unique_id': doc.file_unique_id,
                        'media_type': 'video',
                        'file_size': doc.file_size,
                        'width': None, 'height': None,
                        'duration': None, 'thumbnail_file_id': None
                    }

        return None

    async def save_media_from_message(self, update: Update) -> Optional[int]:
        """
        Salva uma mídia recebida em uma mensagem
        Retorna o ID da mídia salva ou None
        """
        media_info = self.extract_media_info(update)
        if not media_info:
            return None

        media = await prisma.media.create(data={
            "file_id": media_info['file_id'],
            "file_unique_id": media_info['file_unique_id'],
            "media_type": media_info['media_type'],
            "file_size": media_info['file_size'],
            "width": media_info['width'],
            "height": media_info['height'],
            "duration": media_info['duration'],
            "thumbnail_file_id": media_info['thumbnail_file_id'],
        })
        return media.id

    async def send_media_group(self, context: Optional[ContextTypes.DEFAULT_TYPE] = None,
                               chat_id: str = None, media_group: Dict = None,
                               caption: Optional[str] = None,
                               parse_mode: str = 'HTML',
                               reply_markup: Optional[InlineKeyboardMarkup] = None,
                               bot=None, **kwargs) -> bool:
        """Envia um grupo de mídias para um chat"""
        try:
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

            input_medias = []
            for i, media in enumerate(medias):
                media_caption = caption if i == 0 else None
                if media['media_type'] == 'photo':
                    input_medias.append(InputMediaPhoto(
                        media=media['file_id'],
                        caption=media_caption,
                        parse_mode=parse_mode if i == 0 else None
                    ))
                elif media['media_type'] == 'video':
                    input_medias.append(InputMediaVideo(
                        media=media['file_id'],
                        caption=media_caption,
                        parse_mode=parse_mode if i == 0 else None
                    ))

            sent_messages = await bot_instance.send_media_group(chat_id=chat_id, media=input_medias)

            if reply_markup and sent_messages:
                try:
                    if caption:
                        await sent_messages[0].edit_caption(
                            caption=caption, reply_markup=reply_markup, parse_mode=parse_mode
                        )
                        logger.info(f"Botões inline e caption adicionados ao media group {media_group.get('id')}")
                    else:
                        await sent_messages[0].edit_reply_markup(reply_markup=reply_markup)
                        logger.info(f"Botões inline adicionados ao media group {media_group.get('id')} (sem caption)")
                except Exception as e:
                    logger.error(f"Erro ao adicionar botões inline ao media group {media_group.get('id')}: {e}")
                    try:
                        await sent_messages[0].edit_caption(
                            caption=caption if caption else "",
                            reply_markup=reply_markup,
                            parse_mode=parse_mode if caption else None
                        )
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
        """Envia uma única mídia para um chat"""
        try:
            if media['media_type'] == 'photo':
                await context.bot.send_photo(
                    chat_id=chat_id, photo=media['file_id'],
                    caption=caption, parse_mode=parse_mode, reply_markup=reply_markup
                )
            elif media['media_type'] == 'video':
                await context.bot.send_video(
                    chat_id=chat_id, video=media['file_id'],
                    caption=caption, parse_mode=parse_mode, reply_markup=reply_markup
                )
            else:
                logger.warning(f"Tipo de mídia não suportado: {media['media_type']}")
                return False
            return True
        except Exception as e:
            logger.error(f"Erro ao enviar mídia: {e}")
            return False

    def format_media_group_list(self, groups: List[Dict]) -> str:
        """Formata lista de grupos de mídias para exibição"""
        if not groups:
            return "❌ Nenhum grupo de mídias encontrado."

        message = "📦 <b>Grupos de Mídias</b>\n\n"
        for group in groups:
            media_count = group.get('media_count', 0)
            message += f"📦 <b>{group['nome']}</b>\n"
            message += f"   • ID: {group['id']}\n"
            message += f"   • Mídias: {media_count}\n\n"
        return message

    def create_media_group_keyboard(self, groups: List[Dict],
                                    prefix: str = "select_media_group",
                                    show_back: bool = True,
                                    back_callback: str = "voltar_start") -> InlineKeyboardMarkup:
        """Cria teclado inline para listar grupos de mídias"""
        keyboard = []
        for group in groups:
            display_name = f"📦 {group['nome']} ({group.get('media_count', 0)})"
            if len(display_name) > 40:
                display_name = display_name[:37] + "..."
            keyboard.append([InlineKeyboardButton(display_name, callback_data=f"{prefix}_{group['id']}")])

        if show_back:
            keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data=back_callback)])
        return InlineKeyboardMarkup(keyboard)

    async def get_auto_template(self, media_group: Dict) -> Optional[Dict]:
        """
        Busca template automático para um grupo de mídias.
        Se o grupo não tiver template associado, busca qualquer template do canal.
        """
        if media_group.get('template_id'):
            return None
        if not media_group.get('canal_id'):
            return None

        template = await prisma.template.find_first(
            where={"canal_id": media_group['canal_id']},
            include={
                "links": {"order_by": {"ordem": "asc"}},
                "inline_buttons": {"order_by": {"ordem": "asc"}}
            }
        )
        if not template:
            return None
        return {
            "id": template.id,
            "canal_id": template.canal_id,
            "template_mensagem": template.template_mensagem,
            "links": [{"id": l.id, "segmento": l.segmento_com_link, "link": l.link_da_mensagem, "ordem": l.ordem} for l in template.links],
            "inline_buttons": [{"id": b.id, "text": b.button_text, "url": b.button_url, "ordem": b.ordem} for b in template.inline_buttons],
        }

    async def send_media_group_with_template(self,
                                             context: Optional[ContextTypes.DEFAULT_TYPE] = None,
                                             chat_id: str = None,
                                             media_group: Dict = None,
                                             template: Optional[Dict] = None,
                                             global_buttons: Optional[List[Dict]] = None,
                                             use_auto_template: bool = True,
                                             bot=None, **kwargs) -> bool:
        """Envia um grupo de mídias com template e botões aplicados"""
        if not template and use_auto_template:
            auto_template = await self.get_auto_template(media_group)
            if auto_template:
                template = auto_template

        if not global_buttons and media_group.get('canal_id'):
            buttons_raw = await prisma.canalglobalbutton.find_many(
                where={"canal_id": media_group['canal_id']},
                order={"ordem": "asc"}
            )
            global_buttons = [{"id": b.id, "text": b.button_text, "url": b.button_url} for b in buttons_raw] or None

        caption = None
        all_buttons = []

        if template:
            from modules.capture_parse_mode import MessageParser
            parser = MessageParser()
            template_text = template['template_mensagem']
            links = template.get('links', [])
            if links:
                link_tuples = []
                for l in links:
                    # Suporte para objeto Prisma, dicionário ou tupla antiga
                    if hasattr(l, 'segmento_com_link'):
                        link_tuples.append((l.segmento_com_link, l.link_da_mensagem))
                    elif isinstance(l, dict):
                        link_tuples.append((l.get('segmento_com_link', ''), l.get('link_da_mensagem', '')))
                    elif len(l) >= 3:
                        link_tuples.append((l[1], l[2]))
                
                caption = parser.format_message_with_links(template_text, link_tuples)
            else:
                caption = template_text

            for button in template.get('inline_buttons', []):
                if button.get('status') == "ATIVO":
                    all_buttons.append(InlineKeyboardButton(button['text'], url=button['url']))

        if global_buttons:
            for button in global_buttons:
                all_buttons.append(InlineKeyboardButton(button['text'], url=button['url']))

        reply_markup = None
        if all_buttons:
            if len(all_buttons) >= 2:
                button_rows = [[button] for button in all_buttons]
            else:
                button_rows = [all_buttons]
            reply_markup = InlineKeyboardMarkup(button_rows)
            logger.info(f"Preparando {len(all_buttons)} botões inline para media group {media_group.get('id')}")
        else:
            logger.info(f"Nenhum botão inline para media group {media_group.get('id')}")

        return await self.send_media_group(
            context=context, chat_id=chat_id, media_group=media_group,
            caption=caption, reply_markup=reply_markup, bot=bot
        )
