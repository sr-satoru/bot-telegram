import sqlite3
import os
from typing import Optional, List, Tuple, Dict

class Database:
    def __init__(self, db_path: str = "bot_vagas.db"):
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
        
        conn.close()
        
        return {
            'id': template_id_db,
            'canal_id': canal_id,
            'template_mensagem': template_mensagem,
            'links': links,
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
            
            results.append({
                'id': template_id,
                'canal_id': canal_id,
                'template_mensagem': template_mensagem,
                'links': links,
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
        
        conn.close()
        
        return {
            'id': template_id_db,
            'canal_id': canal_id,
            'template_mensagem': template_mensagem,
            'links': links,
            'created_at': created_at
        }
    
    def delete_template(self, template_id: int) -> bool:
        """
        Deleta um template e todos os seus links
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM templates WHERE id = ?', (template_id,))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted

