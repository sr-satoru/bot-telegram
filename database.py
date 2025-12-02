import sqlite3
import os
import logging
from typing import Optional, List, Tuple, Dict

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "bot_postagens_canais.db"):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Retorna uma conexão com o banco de dados"""
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        """Inicializa o banco de dados criando as tabelas necessárias"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Tabela de canais
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS canais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela de IDs dos canais (relação 1:N)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS canal_ids (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                canal_id INTEGER NOT NULL,
                telegram_id TEXT NOT NULL,
                ordem INTEGER NOT NULL,
                FOREIGN KEY (canal_id) REFERENCES canais(id) ON DELETE CASCADE
            )
        ''')
        
        # Tabela de horários (relação 1:N com canais)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS horarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                canal_id INTEGER NOT NULL,
                horario TEXT NOT NULL,
                ordem INTEGER NOT NULL,
                FOREIGN KEY (canal_id) REFERENCES canais(id) ON DELETE CASCADE
            )
        ''')
        
        # Tabela de templates (relação 1:N com canais)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                canal_id INTEGER NOT NULL,
                template_mensagem TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (canal_id) REFERENCES canais(id) ON DELETE CASCADE
            )
        ''')
        
        # Tabela de links dos templates (relação 1:N com templates)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS template_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL,
                segmento_com_link TEXT NOT NULL,
                link_da_mensagem TEXT NOT NULL,
                ordem INTEGER NOT NULL,
                FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE CASCADE
            )
        ''')
        
        # Tabela de botões inline dos templates (relação 1:N com templates)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS template_inline_buttons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL,
                button_text TEXT NOT NULL,
                button_url TEXT NOT NULL,
                ordem INTEGER NOT NULL,
                FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE CASCADE
            )
        ''')
        
        # Tabela de botões inline globais (relação 1:N com canais)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS canal_global_buttons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                canal_id INTEGER NOT NULL,
                button_text TEXT NOT NULL,
                button_url TEXT NOT NULL,
                ordem INTEGER NOT NULL,
                FOREIGN KEY (canal_id) REFERENCES canais(id) ON DELETE CASCADE
            )
        ''')
        
        # Tabela de grupos de mídias
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS media_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                canal_id INTEGER,
                template_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (canal_id) REFERENCES canais(id) ON DELETE SET NULL,
                FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE SET NULL
            )
        ''')
        
        # Tabela de mídias individuais (relação N:N com media_groups)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS medias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT NOT NULL,
                file_unique_id TEXT NOT NULL,
                media_type TEXT NOT NULL,
                file_size INTEGER,
                width INTEGER,
                height INTEGER,
                duration INTEGER,
                thumbnail_file_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela de relação entre media_groups e medias
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS media_group_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_group_id INTEGER NOT NULL,
                media_id INTEGER NOT NULL,
                ordem INTEGER NOT NULL,
                caption TEXT,
                FOREIGN KEY (media_group_id) REFERENCES media_groups(id) ON DELETE CASCADE,
                FOREIGN KEY (media_id) REFERENCES medias(id) ON DELETE CASCADE
            )
        ''')
        
        # Tabela de ciclo de envio de mídias (fila rotativa)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS media_cycle (
                canal_id INTEGER NOT NULL,
                cycle_order TEXT NOT NULL,
                cycle_date TEXT NOT NULL,
                PRIMARY KEY (canal_id, cycle_date),
                FOREIGN KEY (canal_id) REFERENCES canais(id) ON DELETE CASCADE
            )
        ''')
        
        # Tabela de admins
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_canal(self, nome: str, ids_canal: List[str], horarios: List[str], user_id: int) -> int:
        """
        Salva um canal completo com seus IDs e horários
        Retorna o ID do canal criado
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Insere o canal
        cursor.execute('''
            INSERT INTO canais (nome, user_id)
            VALUES (?, ?)
        ''', (nome, user_id))
        
        canal_id = cursor.lastrowid
        
        # Insere os IDs do canal
        for ordem, telegram_id in enumerate(ids_canal, start=1):
            cursor.execute('''
                INSERT INTO canal_ids (canal_id, telegram_id, ordem)
                VALUES (?, ?, ?)
            ''', (canal_id, str(telegram_id), ordem))
        
        # Insere os horários
        for ordem, horario in enumerate(horarios, start=1):
            cursor.execute('''
                INSERT INTO horarios (canal_id, horario, ordem)
                VALUES (?, ?, ?)
            ''', (canal_id, horario, ordem))
        
        conn.commit()
        conn.close()
        
        return canal_id
    
    def get_canal(self, canal_id: int) -> Optional[Dict]:
        """
        Recupera um canal completo com seus IDs e horários
        Retorna um dicionário ou None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Busca o canal
        cursor.execute('''
            SELECT id, nome, user_id, created_at
            FROM canais
            WHERE id = ?
        ''', (canal_id,))
        
        canal_row = cursor.fetchone()
        if not canal_row:
            conn.close()
            return None
        
        canal_id_db, nome, user_id, created_at = canal_row
        
        # Busca os IDs do canal
        cursor.execute('''
            SELECT telegram_id
            FROM canal_ids
            WHERE canal_id = ?
            ORDER BY ordem
        ''', (canal_id_db,))
        
        ids = [row[0] for row in cursor.fetchall()]
        
        # Busca os horários
        cursor.execute('''
            SELECT horario
            FROM horarios
            WHERE canal_id = ?
            ORDER BY ordem
        ''', (canal_id_db,))
        
        horarios = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            'id': canal_id_db,
            'nome': nome,
            'user_id': user_id,
            'ids': ids,
            'horarios': horarios,
            'created_at': created_at
        }
    
    def get_all_canais(self, user_id: Optional[int] = None) -> List[Dict]:
        """
        Recupera todos os canais
        Se user_id for fornecido, retorna apenas os canais desse usuário
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute('''
                SELECT id, nome, user_id, created_at
                FROM canais
                WHERE user_id = ?
                ORDER BY created_at DESC
            ''', (user_id,))
        else:
            cursor.execute('''
                SELECT id, nome, user_id, created_at
                FROM canais
                ORDER BY created_at DESC
            ''')
        
        canais = cursor.fetchall()
        
        results = []
        for canal_id, nome, user_id_db, created_at in canais:
            # Busca IDs
            cursor.execute('''
                SELECT telegram_id
                FROM canal_ids
                WHERE canal_id = ?
                ORDER BY ordem
            ''', (canal_id,))
            ids = [row[0] for row in cursor.fetchall()]
            
            # Busca horários
            cursor.execute('''
                SELECT horario
                FROM horarios
                WHERE canal_id = ?
                ORDER BY ordem
            ''', (canal_id,))
            horarios = [row[0] for row in cursor.fetchall()]
            
            results.append({
                'id': canal_id,
                'nome': nome,
                'user_id': user_id_db,
                'ids': ids,
                'horarios': horarios,
                'created_at': created_at
            })
        
        conn.close()
        return results
    
    def delete_canal(self, canal_id: int) -> bool:
        """
        Deleta um canal e todos os seus dados relacionados
        Retorna True se deletado com sucesso
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM canais WHERE id = ?', (canal_id,))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted
    
    def update_canal(self, canal_id: int, nome: Optional[str] = None, 
                    ids_canal: Optional[List[str]] = None, 
                    horarios: Optional[List[str]] = None) -> bool:
        """
        Atualiza um canal existente
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Atualiza nome se fornecido
        if nome:
            cursor.execute('''
                UPDATE canais SET nome = ? WHERE id = ?
            ''', (nome, canal_id))
        
        # Atualiza IDs se fornecido
        if ids_canal is not None:
            # Remove IDs antigos
            cursor.execute('DELETE FROM canal_ids WHERE canal_id = ?', (canal_id,))
            # Insere novos IDs
            for ordem, telegram_id in enumerate(ids_canal, start=1):
                cursor.execute('''
                    INSERT INTO canal_ids (canal_id, telegram_id, ordem)
                    VALUES (?, ?, ?)
                ''', (canal_id, str(telegram_id), ordem))
        
        # Atualiza horários se fornecido
        if horarios is not None:
            # Remove horários antigos
            cursor.execute('DELETE FROM horarios WHERE canal_id = ?', (canal_id,))
            # Insere novos horários
            for ordem, horario in enumerate(horarios, start=1):
                cursor.execute('''
                    INSERT INTO horarios (canal_id, horario, ordem)
                    VALUES (?, ?, ?)
                ''', (canal_id, horario, ordem))
        
        conn.commit()
        conn.close()
        
        return True
    
    def save_template(self, canal_id: int, template_mensagem: str, links: List[Tuple[str, str]]) -> int:
        """
        Salva um template de mensagem para um canal
        links: Lista de tuplas (segmento_com_link, link_url) na ordem de aparição
        Retorna o ID do template criado
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Insere o template
        cursor.execute('''
            INSERT INTO templates (canal_id, template_mensagem)
            VALUES (?, ?)
        ''', (canal_id, template_mensagem))
        
        template_id = cursor.lastrowid
        
        # Insere os links do template
        for ordem, (segmento, link_url) in enumerate(links, start=1):
            cursor.execute('''
                INSERT INTO template_links (template_id, segmento_com_link, link_da_mensagem, ordem)
                VALUES (?, ?, ?, ?)
            ''', (template_id, segmento, link_url, ordem))
        
        conn.commit()
        conn.close()
        
        return template_id
    
    def get_template(self, template_id: int) -> Optional[Dict]:
        """
        Recupera um template completo com seus links
        Retorna um dicionário ou None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Busca o template
        cursor.execute('''
            SELECT id, canal_id, template_mensagem, created_at
            FROM templates
            WHERE id = ?
        ''', (template_id,))
        
        template_row = cursor.fetchone()
        if not template_row:
            conn.close()
            return None
        
        template_id_db, canal_id, template_mensagem, created_at = template_row
        
        # Busca os links do template
        cursor.execute('''
            SELECT id, segmento_com_link, link_da_mensagem, ordem
            FROM template_links
            WHERE template_id = ?
            ORDER BY ordem
        ''', (template_id_db,))
        
        links = []
        for link_id, segmento, link_url, ordem in cursor.fetchall():
            links.append({
                'id': link_id,
                'segmento': segmento,
                'link': link_url,
                'ordem': ordem
            })
        
        # Busca os botões inline do template
        cursor.execute('''
            SELECT id, button_text, button_url, ordem
            FROM template_inline_buttons
            WHERE template_id = ?
            ORDER BY ordem
        ''', (template_id_db,))
        
        inline_buttons = []
        for button_id, button_text, button_url, ordem in cursor.fetchall():
            inline_buttons.append({
                'id': button_id,
                'text': button_text,
                'url': button_url,
                'ordem': ordem
            })
        
        conn.close()
        
        return {
            'id': template_id_db,
            'canal_id': canal_id,
            'template_mensagem': template_mensagem,
            'links': links,
            'inline_buttons': inline_buttons,
            'created_at': created_at
        }
    
    def get_templates_by_canal(self, canal_id: int) -> List[Dict]:
        """
        Recupera todos os templates de um canal
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, template_mensagem, created_at
            FROM templates
            WHERE canal_id = ?
            ORDER BY created_at DESC
        ''', (canal_id,))
        
        templates = cursor.fetchall()
        results = []
        
        for template_id, template_mensagem, created_at in templates:
            # Busca os links de cada template
            cursor.execute('''
                SELECT segmento_com_link, link_da_mensagem, ordem
                FROM template_links
                WHERE template_id = ?
                ORDER BY ordem
            ''', (template_id,))
            
            links = []
            for segmento, link_url, ordem in cursor.fetchall():
                links.append({
                    'segmento': segmento,
                    'link': link_url,
                    'ordem': ordem
                })
            
            # Busca botões inline de cada template
            cursor.execute('''
                SELECT button_text, button_url, ordem
                FROM template_inline_buttons
                WHERE template_id = ?
                ORDER BY ordem
            ''', (template_id,))
            
            inline_buttons = []
            for button_text, button_url, ordem in cursor.fetchall():
                inline_buttons.append({
                    'text': button_text,
                    'url': button_url,
                    'ordem': ordem
                })
            
            results.append({
                'id': template_id,
                'canal_id': canal_id,
                'template_mensagem': template_mensagem,
                'links': links,
                'inline_buttons': inline_buttons,
                'created_at': created_at
            })
        
        conn.close()
        return results
    
    def update_link(self, link_id: int, link_url: str) -> bool:
        """
        Atualiza o link de um segmento específico
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE template_links
            SET link_da_mensagem = ?
            WHERE id = ?
        ''', (link_url, link_id))
        
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return updated
    
    def update_all_links(self, template_id: int, link_url: str) -> int:
        """
        Atualiza todos os links de um template para o mesmo URL
        Retorna o número de links atualizados
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE template_links
            SET link_da_mensagem = ?
            WHERE template_id = ?
        ''', (link_url, template_id))
        
        count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return count
    
    def get_template_with_link_ids(self, template_id: int) -> Optional[Dict]:
        """
        Recupera um template com IDs dos links (para edição)
        Retorna um dicionário com links como tuplas (link_id, segmento, url, ordem)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Busca o template
        cursor.execute('''
            SELECT id, canal_id, template_mensagem, created_at
            FROM templates
            WHERE id = ?
        ''', (template_id,))
        
        template_row = cursor.fetchone()
        if not template_row:
            conn.close()
            return None
        
        template_id_db, canal_id, template_mensagem, created_at = template_row
        
        # Busca os links do template com IDs
        cursor.execute('''
            SELECT id, segmento_com_link, link_da_mensagem, ordem
            FROM template_links
            WHERE template_id = ?
            ORDER BY ordem
        ''', (template_id_db,))
        
        links = []
        for link_id, segmento, link_url, ordem in cursor.fetchall():
            links.append((link_id, segmento, link_url, ordem))
        
        # Busca botões inline com IDs
        cursor.execute('''
            SELECT id, button_text, button_url, ordem
            FROM template_inline_buttons
            WHERE template_id = ?
            ORDER BY ordem
        ''', (template_id_db,))
        
        inline_buttons = []
        for button_id, button_text, button_url, ordem in cursor.fetchall():
            inline_buttons.append({
                'id': button_id,
                'text': button_text,
                'url': button_url,
                'ordem': ordem
            })
        
        conn.close()
        
        return {
            'id': template_id_db,
            'canal_id': canal_id,
            'template_mensagem': template_mensagem,
            'links': links,
            'inline_buttons': inline_buttons,
            'created_at': created_at
        }
    
    def get_link_info(self, link_id: int) -> Optional[Tuple]:
        """
        Recupera informações de um link pelo ID
        Retorna (link_id, template_id, segmento, url, ordem) ou None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, template_id, segmento_com_link, link_da_mensagem, ordem
            FROM template_links
            WHERE id = ?
        ''', (link_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result
    
    def save_inline_buttons(self, template_id: int, buttons: List[Tuple[str, str]]) -> bool:
        """
        Salva botões inline para um template
        buttons: Lista de tuplas (button_text, button_url)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Remove botões antigos
        cursor.execute('DELETE FROM template_inline_buttons WHERE template_id = ?', (template_id,))
        
        # Insere novos botões
        for ordem, (button_text, button_url) in enumerate(buttons, start=1):
            cursor.execute('''
                INSERT INTO template_inline_buttons (template_id, button_text, button_url, ordem)
                VALUES (?, ?, ?, ?)
            ''', (template_id, button_text, button_url, ordem))
        
        conn.commit()
        conn.close()
        
        return True
    
    def get_inline_buttons(self, template_id: int) -> List[Dict]:
        """
        Recupera botões inline de um template
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, button_text, button_url, ordem
            FROM template_inline_buttons
            WHERE template_id = ?
            ORDER BY ordem
        ''', (template_id,))
        
        buttons = []
        for button_id, button_text, button_url, ordem in cursor.fetchall():
            buttons.append({
                'id': button_id,
                'text': button_text,
                'url': button_url,
                'ordem': ordem
            })
        
        conn.close()
        return buttons
    
    def delete_inline_button(self, button_id: int) -> bool:
        """
        Deleta um botão inline específico
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM template_inline_buttons WHERE id = ?', (button_id,))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted
    
    def save_global_buttons(self, canal_id: int, buttons: List[Tuple[str, str]]) -> bool:
        """
        Salva botões inline globais para um canal
        buttons: Lista de tuplas (button_text, button_url)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Remove botões antigos
        cursor.execute('DELETE FROM canal_global_buttons WHERE canal_id = ?', (canal_id,))
        
        # Insere novos botões
        for ordem, (button_text, button_url) in enumerate(buttons, start=1):
            cursor.execute('''
                INSERT INTO canal_global_buttons (canal_id, button_text, button_url, ordem)
                VALUES (?, ?, ?, ?)
            ''', (canal_id, button_text, button_url, ordem))
        
        conn.commit()
        conn.close()
        
        return True
    
    def get_global_buttons(self, canal_id: int) -> List[Dict]:
        """
        Recupera botões inline globais de um canal
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, button_text, button_url, ordem
            FROM canal_global_buttons
            WHERE canal_id = ?
            ORDER BY ordem
        ''', (canal_id,))
        
        buttons = []
        for button_id, button_text, button_url, ordem in cursor.fetchall():
            buttons.append({
                'id': button_id,
                'text': button_text,
                'url': button_url,
                'ordem': ordem
            })
        
        conn.close()
        return buttons
    
    def delete_global_button(self, button_id: int) -> bool:
        """
        Deleta um botão inline global específico
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM canal_global_buttons WHERE id = ?', (button_id,))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted
    
    def delete_template(self, template_id: int) -> bool:
        """
        Deleta um template e todos os seus links e botões inline
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM templates WHERE id = ?', (template_id,))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted
    
    # ========== MÉTODOS DE MÍDIAS ==========
    
    def save_media(self, file_id: str, file_unique_id: str, media_type: str, 
                   file_size: Optional[int] = None, width: Optional[int] = None,
                   height: Optional[int] = None, duration: Optional[int] = None,
                   thumbnail_file_id: Optional[str] = None) -> int:
        """
        Salva uma mídia individual no banco
        Retorna o ID da mídia salva
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO medias (file_id, file_unique_id, media_type, file_size, 
                              width, height, duration, thumbnail_file_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (file_id, file_unique_id, media_type, file_size, width, height, duration, thumbnail_file_id))
        
        media_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return media_id
    
    def get_media(self, media_id: int) -> Optional[Dict]:
        """
        Recupera uma mídia pelo ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, file_id, file_unique_id, media_type, file_size,
                   width, height, duration, thumbnail_file_id, created_at
            FROM medias
            WHERE id = ?
        ''', (media_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            'id': row[0],
            'file_id': row[1],
            'file_unique_id': row[2],
            'media_type': row[3],
            'file_size': row[4],
            'width': row[5],
            'height': row[6],
            'duration': row[7],
            'thumbnail_file_id': row[8],
            'created_at': row[9]
        }
    
    def create_media_group(self, nome: str, user_id: int, canal_id: Optional[int] = None,
                          template_id: Optional[int] = None) -> int:
        """
        Cria um grupo de mídias
        Retorna o ID do grupo criado
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO media_groups (nome, user_id, canal_id, template_id)
            VALUES (?, ?, ?, ?)
        ''', (nome, user_id, canal_id, template_id))
        
        group_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return group_id
    
    def add_media_to_group(self, media_group_id: int, media_id: int, ordem: int,
                          caption: Optional[str] = None) -> bool:
        """
        Adiciona uma mídia a um grupo
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO media_group_items (media_group_id, media_id, ordem, caption)
            VALUES (?, ?, ?, ?)
        ''', (media_group_id, media_id, ordem, caption))
        
        conn.commit()
        conn.close()
        
        return True
    
    def get_media_group(self, group_id: int) -> Optional[Dict]:
        """
        Recupera um grupo de mídias completo com todas as mídias
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Busca o grupo
        cursor.execute('''
            SELECT id, nome, user_id, canal_id, template_id, created_at
            FROM media_groups
            WHERE id = ?
        ''', (group_id,))
        
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        
        group_id_db, nome, user_id, canal_id, template_id, created_at = row
        
        # Busca as mídias do grupo
        cursor.execute('''
            SELECT m.id, m.file_id, m.file_unique_id, m.media_type, m.file_size,
                   m.width, m.height, m.duration, m.thumbnail_file_id,
                   mgi.ordem, mgi.caption
            FROM media_group_items mgi
            JOIN medias m ON mgi.media_id = m.id
            WHERE mgi.media_group_id = ?
            ORDER BY mgi.ordem
        ''', (group_id_db,))
        
        medias = []
        for row in cursor.fetchall():
            medias.append({
                'id': row[0],
                'file_id': row[1],
                'file_unique_id': row[2],
                'media_type': row[3],
                'file_size': row[4],
                'width': row[5],
                'height': row[6],
                'duration': row[7],
                'thumbnail_file_id': row[8],
                'ordem': row[9],
                'caption': row[10]
            })
        
        conn.close()
        
        return {
            'id': group_id_db,
            'nome': nome,
            'user_id': user_id,
            'canal_id': canal_id,
            'template_id': template_id,
            'medias': medias,
            'created_at': created_at
        }
    
    def get_media_groups_by_user(self, user_id: int, canal_id: Optional[int] = None) -> List[Dict]:
        """
        Recupera todos os grupos de mídias de um usuário
        Se canal_id for fornecido, filtra por canal
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if canal_id:
            cursor.execute('''
                SELECT id, nome, user_id, canal_id, template_id, created_at
                FROM media_groups
                WHERE user_id = ? AND canal_id = ?
                ORDER BY created_at DESC
            ''', (user_id, canal_id))
        else:
            cursor.execute('''
                SELECT id, nome, user_id, canal_id, template_id, created_at
                FROM media_groups
                WHERE user_id = ?
                ORDER BY created_at DESC
            ''', (user_id,))
        
        groups = cursor.fetchall()
        results = []
        
        for group_id, nome, user_id_db, canal_id_db, template_id, created_at in groups:
            # Conta mídias do grupo
            cursor.execute('''
                SELECT COUNT(*) FROM media_group_items WHERE media_group_id = ?
            ''', (group_id,))
            count = cursor.fetchone()[0]
            
            results.append({
                'id': group_id,
                'nome': nome,
                'user_id': user_id_db,
                'canal_id': canal_id_db,
                'template_id': template_id,
                'media_count': count,
                'created_at': created_at
            })
        
        conn.close()
        return results
    
    def delete_media_group(self, group_id: int) -> bool:
        """
        Deleta um grupo de mídias e todas as suas relações
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM media_groups WHERE id = ?', (group_id,))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted
    
    def remove_media_from_group(self, group_id: int, media_id: int) -> bool:
        """
        Remove uma mídia específica de um grupo
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM media_group_items
            WHERE media_group_id = ? AND media_id = ?
        ''', (group_id, media_id))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted
    
    def update_media_group(self, group_id: int, nome: Optional[str] = None,
                          canal_id: Optional[int] = None,
                          template_id: Optional[int] = None,
                          remove_template: bool = False) -> bool:
        """
        Atualiza informações de um grupo de mídias
        remove_template: Se True, remove o template (define como NULL)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if nome is not None:
            updates.append('nome = ?')
            params.append(nome)
        
        if canal_id is not None:
            updates.append('canal_id = ?')
            params.append(canal_id)
        
        if remove_template:
            # Remove template (define como NULL)
            updates.append('template_id = NULL')
        elif template_id is not None:
            updates.append('template_id = ?')
            params.append(template_id)
        
        if not updates:
            conn.close()
            return False
        
        params.append(group_id)
        query = f'UPDATE media_groups SET {", ".join(updates)} WHERE id = ?'
        
        cursor.execute(query, params)
        conn.commit()
        conn.close()
        
        return True
    
    # ========== MÉTODOS DE CICLO DE MÍDIAS (FILA ROTATIVA) ==========
    
    def get_media_cycle(self, canal_id: int, media_groups: List[Dict]) -> List[int]:
        """
        Obtém ou cria o ciclo de mídias para um canal
        Retorna lista de IDs de grupos de mídias em ordem
        """
        import json
        import random
        from datetime import datetime
        
        hoje = datetime.now().strftime('%Y-%m-%d')
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Busca ciclo existente
        cursor.execute('''
            SELECT cycle_order FROM media_cycle
            WHERE canal_id = ? AND cycle_date = ?
        ''', (canal_id, hoje))
        
        row = cursor.fetchone()
        
        if row:
            order = json.loads(row[0])
            # Filtra apenas grupos que ainda existem
            group_ids = [g['id'] for g in media_groups]
            order = [gid for gid in order if gid in group_ids]
            
            # Se o ciclo está vazio ou muito pequeno, recria
            if len(order) < len(media_groups) * 0.1:  # Menos de 10% restantes
                logger.info(f"🔄 Ciclo quase vazio para canal {canal_id}, recriando...")
                ids = [g['id'] for g in media_groups]
                random.shuffle(ids)
                cursor.execute('''
                    UPDATE media_cycle SET cycle_order = ?
                    WHERE canal_id = ? AND cycle_date = ?
                ''', (json.dumps(ids), canal_id, hoje))
                conn.commit()
                conn.close()
                return ids
            conn.close()
            return order
        else:
            # Primeiro ciclo do dia - cria embaralhado
            ids = [g['id'] for g in media_groups]
            random.shuffle(ids)
            cursor.execute('''
                INSERT OR REPLACE INTO media_cycle (canal_id, cycle_order, cycle_date)
                VALUES (?, ?, ?)
            ''', (canal_id, json.dumps(ids), hoje))
            conn.commit()
            conn.close()
            logger.info(f"🆕 Novo ciclo criado para canal {canal_id} com {len(ids)} grupos")
            return ids
    
    def pop_media_cycle(self, canal_id: int, media_groups: List[Dict]) -> Optional[int]:
        """
        Remove e retorna o primeiro grupo da fila (sistema FIFO)
        Quando a fila acaba, recria automaticamente embaralhando
        Retorna o ID do grupo ou None se não houver grupos
        """
        import json
        import random
        from datetime import datetime
        
        hoje = datetime.now().strftime('%Y-%m-%d')
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Busca ciclo atual
        cursor.execute('''
            SELECT cycle_order FROM media_cycle
            WHERE canal_id = ? AND cycle_date = ?
        ''', (canal_id, hoje))
        
        row = cursor.fetchone()
        
        if not row:
            # Cria novo ciclo
            cycle = self.get_media_cycle(canal_id, media_groups)
            if not cycle:
                conn.close()
                return None
            # Recursivamente chama novamente após criar
            return self.pop_media_cycle(canal_id, media_groups)
        
        order = json.loads(row[0])
        
        if not order:
            # Ciclo vazio - recria
            if media_groups and len(media_groups) > 0:
                logger.info(f"🔄 Recriando ciclo com {len(media_groups)} grupos disponíveis...")
                ids = [g['id'] for g in media_groups]
                random.shuffle(ids)
                cursor.execute('''
                    UPDATE media_cycle SET cycle_order = ?
                    WHERE canal_id = ? AND cycle_date = ?
                ''', (json.dumps(ids), canal_id, hoje))
                conn.commit()
                
                # Retorna a primeira do novo ciclo
                if ids:
                    next_id = ids[0]
                    remaining_ids = ids[1:]
                    cursor.execute('''
                        UPDATE media_cycle SET cycle_order = ?
                        WHERE canal_id = ? AND cycle_date = ?
                    ''', (json.dumps(remaining_ids), canal_id, hoje))
                    conn.commit()
                    conn.close()
                    logger.info(f"✅ Novo ciclo criado e primeiro grupo {next_id} selecionado")
                    return next_id
            conn.close()
            return None
        
        # Pega o primeiro da fila (FIFO)
        next_id = order.pop(0)
        
        # Atualiza a fila removendo o primeiro
        cursor.execute('''
            UPDATE media_cycle SET cycle_order = ?
            WHERE canal_id = ? AND cycle_date = ?
        ''', (json.dumps(order), canal_id, hoje))
        conn.commit()
        conn.close()
        
        # Log de progresso
        total_restante = len(order)
        if total_restante <= 3:
            logger.info(f"⚠️ Poucos grupos restantes no ciclo: {total_restante}")
        
        return next_id
    
    # ========== MÉTODOS DE ADMINISTRADORES ==========
    
    def add_admin(self, user_id: int, username: Optional[str] = None) -> bool:
        """
        Adiciona um admin ao banco de dados
        Retorna True se adicionado com sucesso, False se já existir
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO admins (user_id, username)
                VALUES (?, ?)
            ''', (user_id, username))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            # Admin já existe
            conn.close()
            return False
    
    def remove_admin(self, user_id: int) -> bool:
        """
        Remove um admin do banco de dados
        Retorna True se removido com sucesso
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM admins WHERE user_id = ?', (user_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted
    
    def is_admin(self, user_id: int) -> bool:
        """
        Verifica se um usuário é admin
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,))
        result = cursor.fetchone() is not None
        conn.close()
        
        return result
    
    def get_all_admins(self) -> List[Dict]:
        """
        Retorna lista de todos os admins
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, username, created_at
            FROM admins
            ORDER BY created_at DESC
        ''')
        
        admins = []
        for user_id, username, created_at in cursor.fetchall():
            admins.append({
                'user_id': user_id,
                'username': username,
                'created_at': created_at
            })
        
        conn.close()
        return admins
    
    def get_admin(self, user_id: int) -> Optional[Dict]:
        """
        Retorna informações de um admin específico
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, username, created_at
            FROM admins
            WHERE user_id = ?
        ''', (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            'user_id': row[0],
            'username': row[1],
            'created_at': row[2]
        }

