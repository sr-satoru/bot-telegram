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

