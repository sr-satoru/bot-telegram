"""
Módulo para agendamento e envio automático de mídias para canais
"""

import logging
import asyncio
from datetime import datetime, time
from typing import List, Dict, Optional
from database import Database
from media_handler import MediaHandler

logger = logging.getLogger(__name__)

class MediaScheduler:
    """Classe para gerenciar agendamento e envio automático de mídias"""
    
    def __init__(self, database: Database, media_handler: MediaHandler, bot):
        self.db = database
        self.media_handler = media_handler
        self.bot = bot
        self.running = False
        # Último horário processado por canal: {canal_id: {horario: timestamp}}
        self.last_sent = {}
    
    def parse_time(self, time_str: str) -> Optional[time]:
        """Converte string de horário (HH:MM) para objeto time"""
        try:
            parts = time_str.strip().split(':')
            if len(parts) == 2:
                hour = int(parts[0])
                minute = int(parts[1])
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return time(hour, minute)
        except (ValueError, IndexError):
            pass
        return None
    
    def should_send_now(self, horario_str: str) -> bool:
        """Verifica se é hora de enviar baseado no horário configurado"""
        horario = self.parse_time(horario_str)
        if not horario:
            return False
        
        agora = datetime.now()
        # Compara hora e minuto (ignora segundos)
        # Considera que está no horário se estiver no minuto exato (primeiros 30 segundos do minuto)
        return agora.hour == horario.hour and agora.minute == horario.minute and agora.second < 30
    
    def was_sent_in_this_minute(self, canal_id: int, horario: str) -> bool:
        """Verifica se já foi enviado neste minuto para evitar duplicatas"""
        key = f"{canal_id}_{horario}"
        if key not in self.last_sent:
            return False
        
        agora = datetime.now()
        ultimo_envio = self.last_sent[key]
        
        # Verifica se foi no mesmo minuto
        return (agora.hour == ultimo_envio.hour and 
                agora.minute == ultimo_envio.minute)
    
    def mark_as_sent(self, canal_id: int, horario: str):
        """Marca como enviado neste minuto"""
        key = f"{canal_id}_{horario}"
        self.last_sent[key] = datetime.now()
    
    async def send_media_group_to_channel(self, canal_id: int, group: Dict, template: Optional[Dict] = None):
        """Envia um grupo de mídias para um canal específico"""
        try:
            # Busca IDs do canal
            canal_data = self.db.get_canal(canal_id)
            if not canal_data:
                logger.error(f"Canal {canal_id} não encontrado")
                return False
            
            canal_telegram_ids = canal_data.get('ids', [])
            if not canal_telegram_ids:
                logger.warning(f"Canal {canal_id} não tem IDs configurados")
                return False
            
            # Busca botões globais do canal
            global_buttons = self.db.get_global_buttons(canal_id)
            if not global_buttons:
                global_buttons = None
            
            # Se não tem template, busca automaticamente
            if not template:
                auto_template = self.media_handler.get_auto_template(group, self.db)
                if auto_template:
                    template = auto_template
            
            # Envia para todos os IDs do canal
            success_count = 0
            for telegram_id in canal_telegram_ids:
                try:
                    success = await self.media_handler.send_media_group_with_template(
                        context=None,  # Não precisa de context para envio direto
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
                        logger.info(f"✅ Mídia enviada para canal {telegram_id} (grupo {group.get('id')})")
                    else:
                        logger.warning(f"⚠️ Falha ao enviar mídia para canal {telegram_id}")
                        
                except Exception as e:
                    logger.error(f"❌ Erro ao enviar para canal {telegram_id}: {e}")
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar grupo de mídias: {e}")
            return False
    
    async def check_and_send_scheduled(self):
        """Verifica horários e envia mídias agendadas"""
        try:
            # Busca todos os canais
            canais = self.db.get_all_canais()
            
            for canal in canais:
                canal_id = canal['id']
                horarios = canal.get('horarios', [])
                
                if not horarios:
                    continue
                
                # Verifica cada horário
                for horario_str in horarios:
                    if not self.should_send_now(horario_str):
                        continue
                    
                    # Verifica se já foi enviado neste minuto (evita duplicatas)
                    if self.was_sent_in_this_minute(canal_id, horario_str):
                        logger.info(f"⏭️ Já foi enviado para canal {canal_id} no horário {horario_str} neste minuto")
                        continue
                    
                    # Busca grupos de mídias do canal
                    user_id = canal.get('user_id')
                    media_groups = self.db.get_media_groups_by_user(user_id, canal_id)
                    
                    if not media_groups:
                        logger.info(f"Nenhum grupo de mídias para canal {canal_id} no horário {horario_str}")
                        continue
                    
                    # Sistema de fila rotativa: pega apenas o primeiro da fila
                    next_group_id = self.db.pop_media_cycle(canal_id, media_groups)
                    
                    if not next_group_id:
                        logger.warning(f"Nenhum grupo disponível na fila para canal {canal_id}")
                        continue
                    
                    # Busca grupo completo
                    group = self.db.get_media_group(next_group_id)
                    if not group or not group.get('medias'):
                        logger.warning(f"Grupo {next_group_id} não encontrado ou vazio")
                        continue
                    
                    # Busca template se houver associado
                    template = None
                    if group.get('template_id'):
                        template = self.db.get_template(group['template_id'])
                    
                    # Envia apenas o primeiro grupo da fila
                    logger.info(f"📤 Enviando grupo {next_group_id} da fila para canal {canal_id} no horário {horario_str}")
                    success = await self.send_media_group_to_channel(canal_id, group, template)
                    
                    if success:
                        self.mark_as_sent(canal_id, horario_str)
                        logger.info(f"✅ Grupo {next_group_id} enviado com sucesso. Fila rotacionada automaticamente.")
                    else:
                        logger.error(f"❌ Falha ao enviar grupo {next_group_id} para canal {canal_id}")
                    
        except Exception as e:
            logger.error(f"❌ Erro ao verificar agendamentos: {e}")
    
    async def run_scheduler(self):
        """Executa o scheduler em loop contínuo"""
        self.running = True
        logger.info("🚀 Scheduler de mídias iniciado!")
        
        while self.running:
            try:
                # Verifica a cada minuto
                await self.check_and_send_scheduled()
                
                # Limpa controle de envios do minuto anterior (a cada minuto)
                # O sistema de fila já gerencia automaticamente a rotação
                
                # Aguarda 60 segundos antes da próxima verificação
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"❌ Erro no scheduler: {e}")
                await asyncio.sleep(60)
    
    def stop(self):
        """Para o scheduler"""
        self.running = False
        logger.info("🛑 Scheduler de mídias parado")

