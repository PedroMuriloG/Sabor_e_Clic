import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()

DB_NAME = "database.db"


class DatabaseConnection:
  """Classe para gerenciar a conexão com o SQLite de forma segura e limpa (evita repetição de .close() e .commit())"""

  def __init__(self, db_name=DB_NAME):
    self.db_name = db_name
    self.conn = None
    self.cursor = None

  def __enter__(self):
    # Abre a conexão e o cursor automaticamente ao entrar no bloco 'with'
    self.conn = sqlite3.connect(self.db_name)
    self.conn.row_factory = sqlite3.Row  # Permite acessar colunas por nome
    self.cursor = self.conn.cursor()
    return self.cursor

  def __exit__(self, exc_type, exc_val, exc_tb):
    # Se ocorreu algum erro, desfaz (rollback). Se deu tudo certo, salva (commit)
    if exc_type is not None:
      self.conn.rollback()
    else:
      self.conn.commit()

    # Fecha o cursor e a conexão automaticamente ao sair do bloco 'with'
    self.cursor.close()
    self.conn.close()