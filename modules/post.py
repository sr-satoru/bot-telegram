"""
Scheduler otimizado para agendamento e envio automático de mídias
"""

import logging
import asyncio
import json
import random
from datetime import datetime
from typing import List, Dict, Optional
from db import prisma
from media_handler import MediaHandler

# Timezone de Brasília
try:
    from zoneinfo import ZoneInfo
    BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")
except ImportError:
    try:
        import pytz
        BRASILIA_TZ = pytz.timezone("America/Sao_Paulo")
    except ImportError:
        from datetime import timedelta, timezone
        BRASILIA_TZ = timezone(timedelta(hours=-3))

logger = logging.getLogger(__name__)


class MediaScheduler:
    """Scheduler otimizado para envio automático de mídias"""

    def __init__(self, media_handler: MediaHandler, bot):
        self.media_handler = media_handler
        self.bot = bot
        self.running = False

    def _get_now(self) -> datetime:
        """Retorna horário atual em Brasília"""
        return datetime.now(BRASILIA_TZ)

    def _get_today(self) -> str:
        """Retorna data de hoje no formato YYYY-MM-DD"""
        return self._get_now().strftime('%Y-%m-%d')

    def _should_send_now(self, horario: str) -> bool:
        """Verifica se é hora de enviar"""
        return self._get_now().strftime('%H:%M') == horario

    async def _ja_enviou_hoje(self, canal_id: int, horario: str) -> bool:
        """Verifica se já enviou neste horário hoje"""
        hoje = self._get_today()
        result = await prisma.sentschedule.find_first(
            where={"canal_id": canal_id, "horario": horario, "date": hoje}
        )
        return result is not None

    async def _registrar_envio(self, canal_id: int, horario: str):
        """Registra envio no banco"""
        hoje = self._get_today()
        try:
            await prisma.sentschedule.create(
                data={"canal_id": canal_id, "horario": horario, "date": hoje}
            )
        except Exception:
            pass  # Ignora duplicatas (registro já existe)

    async def _pop_cycle(self, canal_id: int, media_groups: List[Dict]) -> Optional[int]:
        """Remove e retorna primeiro grupo da fila"""
        hoje = self._get_today()

        cycle = await prisma.mediacycle.find_first(
            where={"canal_id": canal_id, "cycle_date": hoje}
        )

        if not cycle:
            # Cria novo ciclo
            ids = [g['id'] for g in media_groups]
            if not ids:
                return None
            random.shuffle(ids)
            next_id = ids.pop(0)
            await prisma.mediacycle.create(
                data={"canal_id": canal_id, "cycle_order": json.dumps(ids), "cycle_date": hoje}
            )
            return next_id

        order = json.loads(cycle.cycle_order)

        if not order:
            # Recria ciclo
            ids = [g['id'] for g in media_groups]
            if not ids:
                return None
            random.shuffle(ids)
            next_id = ids.pop(0)
            await prisma.mediacycle.update(
                where={"canal_id_cycle_date": {"canal_id": canal_id, "cycle_date": hoje}},
                data={"cycle_order": json.dumps(ids)}
            )
            return next_id

        # Remove primeiro
        next_id = order.pop(0)
        await prisma.mediacycle.update(
            where={"canal_id_cycle_date": {"canal_id": canal_id, "cycle_date": hoje}},
            data={"cycle_order": json.dumps(order)}
        )
        return next_id

    async def _get_canal_data(self, canal_id: int) -> Optional[Dict]:
        """Busca dados do canal com IDs e horários"""
        canal = await prisma.canal.find_unique(
            where={"id": canal_id},
            include={"ids": True, "horarios": {"order_by": {"ordem": "asc"}}}
        )
        if not canal:
            return None
        return {
            "id": canal.id,
            "nome": canal.nome,
            "user_id": canal.user_id,
            "ids": [c.telegram_id for c in canal.ids],
            "horarios": [h.horario for h in canal.horarios],
        }

    async def _get_media_groups_by_canal(self, user_id: int, canal_id: int) -> List[Dict]:
        """Busca grupos de mídia de um canal"""
        groups = await prisma.mediagroup.find_many(
            where={"user_id": user_id, "canal_id": canal_id},
            include={"items": True},
            order={"created_at": "desc"}
        )
        return [{"id": g.id, "nome": g.nome, "template_id": g.template_id,
                 "canal_id": g.canal_id, "media_count": len(g.items)} for g in groups]

    async def _get_media_group_full(self, group_id: int) -> Optional[Dict]:
        """Busca grupo completo com mídias"""
        group = await prisma.mediagroup.find_unique(
            where={"id": group_id},
            include={"items": {"include": {"media": True}, "order_by": {"ordem": "asc"}}}
        )
        if not group:
            return None
        medias = []
        for item in group.items:
            m = item.media
            medias.append({
                "id": m.id, "file_id": m.file_id, "file_unique_id": m.file_unique_id,
                "media_type": m.media_type, "file_size": m.file_size,
                "width": m.width, "height": m.height, "duration": m.duration,
                "thumbnail_file_id": m.thumbnail_file_id,
                "ordem": item.ordem, "caption": item.caption
            })
        return {
            "id": group.id, "nome": group.nome, "user_id": group.user_id,
            "canal_id": group.canal_id, "template_id": group.template_id,
            "medias": medias
        }

    async def _get_template(self, template_id: int) -> Optional[Dict]:
        """Busca template com links e botões"""
        t = await prisma.template.find_unique(
            where={"id": template_id},
            include={
                "links": {"order_by": {"ordem": "asc"}},
                "inline_buttons": {"order_by": {"ordem": "asc"}}
            }
        )
        if not t:
            return None
        return {
            "id": t.id, "canal_id": t.canal_id,
            "template_mensagem": t.template_mensagem,
            "links": [{"id": l.id, "segmento": l.segmento_com_link, "link": l.link_da_mensagem, "ordem": l.ordem} for l in t.links],
            "inline_buttons": [
                {
                    "id": b.id, "text": b.button_text, "url": b.button_url, 
                    "ordem": b.ordem, "status": b.status, 
                    "icon_emoji_id": b.icon_emoji_id, "style": b.button_style
                } 
                for b in t.inline_buttons
            ],
        }

    async def _get_global_buttons(self, canal_id: int) -> List[Dict]:
        """Busca botões globais de um canal"""
        buttons = await prisma.canalglobalbutton.find_many(
            where={"canal_id": canal_id},
            order={"ordem": "asc"}
        )
        return [{"id": b.id, "text": b.button_text, "url": b.button_url, "ordem": b.ordem, "icon_emoji_id": b.icon_emoji_id, "style": b.button_style} for b in buttons]

    async def limpar_registros_antigos(self):
        """Remove registros de envios e ciclos antigos (mais de 1 dia)"""
        from datetime import timedelta
        ontem = (self._get_now() - timedelta(days=1)).date().isoformat()

        sent = await prisma.sentschedule.delete_many(where={"date": {"lt": ontem}})
        cycles = await prisma.mediacycle.delete_many(where={"cycle_date": {"lt": ontem}})

        if sent > 0 or cycles > 0:
            logger.info(f"🧹 Limpeza: {sent} envios e {cycles} ciclos antigos removidos")

    async def _enviar_midia(self, canal_id: int, group: Dict, template: Optional[Dict] = None) -> bool:
        """Envia mídia para o canal"""
        try:
            canal_data = await self._get_canal_data(canal_id)
            if not canal_data or not canal_data.get('ids'):
                return False

            global_buttons = await self._get_global_buttons(canal_id) or None

            if not template and group.get('template_id'):
                template = await self._get_template(group['template_id'])

            if not template:
                template = await self.media_handler.get_auto_template(group)

            success_count = 0
            for telegram_id in canal_data['ids']:
                try:
                    success = await self.media_handler.send_media_group_with_template(
                        context=None,
                        chat_id=telegram_id,
                        media_group=group,
                        template=template,
                        global_buttons=global_buttons,
                        use_auto_template=True,
                        bot=self.bot
                    )
                    if success:
                        success_count += 1
                except Exception as e:
                    logger.error(f"Erro ao enviar para {telegram_id}: {e}")

            return success_count > 0
        except Exception as e:
            logger.error(f"Erro ao enviar mídia: {e}")
            return False

    async def _processar_canal(self, canal: Dict):
        """Processa um canal e envia se necessário"""
        canal_id = canal['id']
        horarios = canal.get('horarios', [])

        if not horarios:
            return

        for horario in horarios:
            if not self._should_send_now(horario):
                continue

            if await self._ja_enviou_hoje(canal_id, horario):
                continue

            user_id = canal.get('user_id')
            media_groups = await self._get_media_groups_by_canal(user_id, canal_id)

            if not media_groups:
                continue

            next_group_id = await self._pop_cycle(canal_id, media_groups)
            if not next_group_id:
                continue

            group = await self._get_media_group_full(next_group_id)
            if not group or not group.get('medias'):
                continue

            template = None
            if group.get('template_id'):
                template = await self._get_template(group['template_id'])

            success = await self._enviar_midia(canal_id, group, template)
            if success:
                await self._registrar_envio(canal_id, horario)
                logger.info(f"✅ Enviado: canal {canal_id} às {horario}")

    async def check_and_send(self):
        """Verifica e envia mídias agendadas"""
        try:
            canais_raw = await prisma.canal.find_many(
                include={"ids": True, "horarios": {"order_by": {"ordem": "asc"}}}
            )
            canais = [
                {
                    "id": c.id, "nome": c.nome, "user_id": c.user_id,
                    "ids": [ci.telegram_id for ci in c.ids],
                    "horarios": [h.horario for h in c.horarios],
                }
                for c in canais_raw
            ]
            for canal in canais:
                await self._processar_canal(canal)
        except Exception as e:
            logger.error(f"Erro no scheduler: {e}")

    async def run_scheduler(self):
        """Executa o scheduler em loop"""
        self.running = True
        logger.info("🚀 Scheduler iniciado")

        last_cleanup = self._get_now()

        while self.running:
            try:
                # Limpeza automática a cada 6 horas
                agora = self._get_now()
                if (agora - last_cleanup).total_seconds() > 21600:
                    await self.limpar_registros_antigos()
                    last_cleanup = agora

                await self.check_and_send()
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Erro no loop: {e}")
                await asyncio.sleep(60)
