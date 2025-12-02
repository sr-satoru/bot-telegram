import sqlite3
import os
from typing import Optional, List, Tuple

class Database:
    def __init__(self, db_path: str = "bot_database.db"):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Retorna uma conexão com o banco de dados"""
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        """Inicializa o banco de dados criando as tabelas necessárias"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Verifica se precisa fazer migração da estrutura antiga
        self._migrate_database(cursor)
        
        # Tabela de templates
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_mensagem TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela de links (relação 1:N com templates)
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
    
    def _migrate_database(self, cursor):
        """Migra o banco de dados da estrutura antiga para a nova"""
        try:
            # Verifica se a tabela templates existe e tem as colunas antigas
            cursor.execute("PRAGMA table_info(templates)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Se tem as colunas antigas (segmento_com_link, link_da_mensagem), precisa migrar
            if 'segmento_com_link' in columns and 'link_da_mensagem' in columns:
                # Busca todos os templates antigos
                cursor.execute('''
                    SELECT id, template_mensagem, segmento_com_link, link_da_mensagem, created_at
                    FROM templates
                ''')
                old_templates = cursor.fetchall()
                
                # Cria a nova estrutura
                cursor.execute('DROP TABLE IF EXISTS templates_old')
                cursor.execute('DROP TABLE IF EXISTS template_links')
                
                # Renomeia a tabela antiga
                cursor.execute('ALTER TABLE templates RENAME TO templates_old')
                
                # Cria a nova tabela templates
                cursor.execute('''
                    CREATE TABLE templates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        template_mensagem TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Cria a tabela template_links
                cursor.execute('''
                    CREATE TABLE template_links (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        template_id INTEGER NOT NULL,
                        segmento_com_link TEXT NOT NULL,
                        link_da_mensagem TEXT NOT NULL,
                        ordem INTEGER NOT NULL,
                        FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE CASCADE
                    )
                ''')
                
                # Migra os dados
                for old_id, template_msg, segmento, link_url, created_at in old_templates:
                    # Insere na nova tabela templates
                    cursor.execute('''
                        INSERT INTO templates (id, template_mensagem, created_at)
                        VALUES (?, ?, ?)
                    ''', (old_id, template_msg, created_at))
                    
                    # Insere na tabela template_links
                    cursor.execute('''
                        INSERT INTO template_links (template_id, segmento_com_link, link_da_mensagem, ordem)
                        VALUES (?, ?, ?, ?)
                    ''', (old_id, segmento, link_url, 1))
                
                # Remove a tabela antiga
                cursor.execute('DROP TABLE templates_old')
                
        except sqlite3.OperationalError:
            # Se a tabela não existe ainda, não precisa migrar
            pass
    
    def save_template(self, template_mensagem: str, links: List[Tuple[str, str]]) -> int:
        """
        Salva um template no banco de dados com múltiplos links
        links: Lista de tuplas (segmento_com_link, link_da_mensagem)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Insere o template
        cursor.execute('''
            INSERT INTO templates (template_mensagem)
            VALUES (?)
        ''', (template_mensagem,))
        
        template_id = cursor.lastrowid
        
        # Insere os links
        for ordem, (segmento, link_url) in enumerate(links, start=1):
            cursor.execute('''
                INSERT INTO template_links (template_id, segmento_com_link, link_da_mensagem, ordem)
                VALUES (?, ?, ?, ?)
            ''', (template_id, segmento, link_url, ordem))
        
        conn.commit()
        conn.close()
        
        return template_id
    
    def get_template(self, template_id: int) -> Optional[dict]:
        """
        Recupera um template pelo ID com todos os seus links
        Retorna um dicionário: {'id': int, 'template_mensagem': str, 'links': [(segmento, url), ...]}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Busca o template
        cursor.execute('''
            SELECT id, template_mensagem, created_at
            FROM templates
            WHERE id = ?
        ''', (template_id,))
        
        template_row = cursor.fetchone()
        if not template_row:
            conn.close()
            return None
        
        template_id, template_mensagem, created_at = template_row
        
        # Busca os links do template
        cursor.execute('''
            SELECT segmento_com_link, link_da_mensagem
            FROM template_links
            WHERE template_id = ?
            ORDER BY ordem
        ''', (template_id,))
        
        links = cursor.fetchall()
        conn.close()
        
        return {
            'id': template_id,
            'template_mensagem': template_mensagem,
            'links': links,
            'created_at': created_at
        }
    
    def get_all_templates(self) -> List[dict]:
        """Recupera todos os templates com seus links"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Busca todos os templates
        cursor.execute('''
            SELECT id, template_mensagem, created_at
            FROM templates
            ORDER BY created_at DESC
        ''')
        
        templates = cursor.fetchall()
        
        # Para cada template, busca seus links
        results = []
        for template_id, template_mensagem, created_at in templates:
            cursor.execute('''
                SELECT segmento_com_link, link_da_mensagem
                FROM template_links
                WHERE template_id = ?
                ORDER BY ordem
            ''', (template_id,))
            
            links = cursor.fetchall()
            results.append({
                'id': template_id,
                'template_mensagem': template_mensagem,
                'links': links,
                'created_at': created_at
            })
        
        conn.close()
        return results
    
    def get_template_with_link_ids(self, template_id: int) -> Optional[dict]:
        """
        Recupera um template pelo ID com todos os seus links incluindo IDs dos links
        Retorna um dicionário: {'id': int, 'template_mensagem': str, 'links': [(link_id, segmento, url, ordem), ...]}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Busca o template
        cursor.execute('''
            SELECT id, template_mensagem, created_at
            FROM templates
            WHERE id = ?
        ''', (template_id,))
        
        template_row = cursor.fetchone()
        if not template_row:
            conn.close()
            return None
        
        template_id, template_mensagem, created_at = template_row
        
        # Busca os links do template com IDs
        cursor.execute('''
            SELECT id, segmento_com_link, link_da_mensagem, ordem
            FROM template_links
            WHERE template_id = ?
            ORDER BY ordem
        ''', (template_id,))
        
        links = cursor.fetchall()
        conn.close()
        
        return {
            'id': template_id,
            'template_mensagem': template_mensagem,
            'links': links,  # [(link_id, segmento, url, ordem), ...]
            'created_at': created_at
        }
    
    def update_link(self, link_id: int, new_url: str) -> bool:
        """
        Atualiza o URL de um link específico
        Retorna True se atualizado com sucesso, False caso contrário
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE template_links
            SET link_da_mensagem = ?
            WHERE id = ?
        ''', (new_url, link_id))
        
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return updated
    
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
    
    def update_all_links(self, template_id: int, new_url: str) -> int:
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
        ''', (new_url, template_id))
        
        updated_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return updated_count


