"""
Scheduler otimizado para agendamento e envio automático de mídias
"""

import logging
import asyncio
import json
import random
from datetime import datetime
from typing import List, Dict, Optional
from database import Database
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
    
    def __init__(self, database: Database, media_handler: MediaHandler, bot):
        self.db = database
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
    
    def _ja_enviou_hoje(self, canal_id: int, horario: str) -> bool:
        """Verifica se já enviou neste horário hoje"""
        hoje = self._get_today()
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM sent_schedules WHERE canal_id = ? AND horario = ? AND date = ?",
            (canal_id, horario, hoje)
        )
        result = cursor.fetchone() is not None
        conn.close()
        return result
    
    def _registrar_envio(self, canal_id: int, horario: str):
        """Registra envio no banco"""
        hoje = self._get_today()
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO sent_schedules (canal_id, horario, date) VALUES (?, ?, ?)",
            (canal_id, horario, hoje)
        )
        conn.commit()
        conn.close()
    
    def _pop_cycle(self, canal_id: int, media_groups: List[Dict]) -> Optional[int]:
        """Remove e retorna primeiro grupo da fila"""
        hoje = self._get_today()
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Busca ciclo atual
        cursor.execute(
            "SELECT cycle_order FROM media_cycle WHERE canal_id = ? AND cycle_date = ?",
            (canal_id, hoje)
        )
        row = cursor.fetchone()
        
        if not row:
            # Cria novo ciclo
            ids = [g['id'] for g in media_groups]
            if not ids:
                conn.close()
                return None
            random.shuffle(ids)
            # Remove primeiro e salva o restante
            next_id = ids.pop(0)
            cursor.execute(
                "INSERT OR REPLACE INTO media_cycle (canal_id, cycle_order, cycle_date) VALUES (?, ?, ?)",
                (canal_id, json.dumps(ids), hoje)
            )
            conn.commit()
            conn.close()
            return next_id
        
        order = json.loads(row[0])
        
        if not order:
            # Recria ciclo
            ids = [g['id'] for g in media_groups]
            if not ids:
                conn.close()
                return None
            random.shuffle(ids)
            # Remove primeiro e salva o restante
            next_id = ids.pop(0)
            cursor.execute(
                "UPDATE media_cycle SET cycle_order = ? WHERE canal_id = ? AND cycle_date = ?",
                (json.dumps(ids), canal_id, hoje)
            )
            conn.commit()
            conn.close()
            return next_id
        
        # Remove primeiro
        next_id = order.pop(0)
        cursor.execute(
            "UPDATE media_cycle SET cycle_order = ? WHERE canal_id = ? AND cycle_date = ?",
            (json.dumps(order), canal_id, hoje)
        )
        conn.commit()
        conn.close()
        return next_id
    
    async def _enviar_midia(self, canal_id: int, group: Dict, template: Optional[Dict] = None) -> bool:
        """Envia mídia para o canal"""
        try:
            canal_data = self.db.get_canal(canal_id)
            if not canal_data or not canal_data.get('ids'):
                return False
            
            global_buttons = self.db.get_global_buttons(canal_id) or None
            
            if not template and group.get('template_id'):
                template = self.db.get_template(group['template_id'])
            
            if not template:
                template = self.media_handler.get_auto_template(group, self.db)
            
            success_count = 0
            for telegram_id in canal_data['ids']:
                try:
                    success = await self.media_handler.send_media_group_with_template(
                        context=None,
                        chat_id=telegram_id,
                        media_group=group,
                        template=template,
                        global_buttons=global_buttons,
                        database=self.db,
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
            
            if self._ja_enviou_hoje(canal_id, horario):
                continue
            
            user_id = canal.get('user_id')
            media_groups = self.db.get_media_groups_by_user(user_id, canal_id)
            
            if not media_groups:
                continue
            
            next_group_id = self._pop_cycle(canal_id, media_groups)
            if not next_group_id:
                continue
            
            group = self.db.get_media_group(next_group_id)
            if not group or not group.get('medias'):
                continue
            
            template = None
            if group.get('template_id'):
                template = self.db.get_template(group['template_id'])
            
            success = await self._enviar_midia(canal_id, group, template)
            if success:
                self._registrar_envio(canal_id, horario)
                logger.info(f"✅ Enviado: canal {canal_id} às {horario}")
    
    async def check_and_send(self):
        """Verifica e envia mídias agendadas"""
        try:
            canais = self.db.get_all_canais()
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
                    self.db.limpar_registros_antigos()
                    last_cleanup = agora
                
                await self.check_and_send()
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Erro no loop: {e}")
                await asyncio.sleep(60)
    
