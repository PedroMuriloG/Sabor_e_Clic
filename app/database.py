from flask import g, has_app_context
import sqlite3

class DatabaseConnection:
    def __init__(self, db_path="banco.db"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None

    def __enter__(self):
        # Se estiver rodando dentro de uma requisição web, usa o 'g'
        if has_app_context():
            if 'db' not in g:
                g.db = sqlite3.connect(self.db_path, timeout=30.0)
                g.db.row_factory = sqlite3.Row
                g.db.execute("PRAGMA journal_mode=WAL;")
            self.conn = g.db
        else:
            # Se estiver rodando fora (ex: script iniciar_db.py no terminal)
            self.conn = sqlite3.connect(self.db_path, timeout=30.0)
            self.conn.row_factory = sqlite3.Row
            
        self.cursor = self.conn.cursor()
        # Retorna o cursor diretamente para que chamadas como 'cursor.execute()' funcionem perfeitamente!
        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.conn.rollback()
        else:
            self.conn.commit()
        self.cursor.close()
        
        # Se não estiver no contexto web, fecha a conexão para não deixar aberta no script
        if not has_app_context():
            self.conn.close()