from app.database import DatabaseConnection

class Ingrediente:
    def __init__(self, nome, quantidade_estoque, id=None):
        self.id = id
        self.nome = nome
        self.quantidade_estoque = quantidade_estoque

    @staticmethod
    def get_all():
        with DatabaseConnection() as cursor:
            cursor.execute("SELECT id, nome, quantidade_estoque FROM ingredientes")
            rows = cursor.fetchall()
            return [Ingrediente(id=r["id"], nome=r["nome"], quantidade_estoque=r["quantidade_estoque"]) for r in rows]

    @staticmethod
    def atualizar_estoque(ingrediente_id, quantidade_adicionada):
        with DatabaseConnection() as cursor:
            cursor.execute("""
                UPDATE ingredientes 
                SET quantidade_estoque = quantidade_estoque + ? 
                WHERE id = ?
            """, (quantidade_adicionada, ingrediente_id))