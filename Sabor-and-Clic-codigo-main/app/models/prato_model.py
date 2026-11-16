from app.database import DatabaseConnection

class Prato:
    def __init__(self, nome, preco, tempo_preparo, foto_url, bancada_id, id=None):
        self.id = id
        self.nome = nome
        self.preco = preco
        self.tempo_preparo = tempo_preparo
        self.foto_url = foto_url
        self.bancada_id = bancada_id

    @staticmethod
    def get_disponiveis_por_bancada(bancada_id):
        """Retorna apenas pratos cujos ingredientes tenham estoque > 0"""
        with DatabaseConnection() as cursor:
            cursor.execute("""
                SELECT DISTINCT p.id, p.nome, p.preco, p.tempo_preparo, p.foto_url, p.bancada_id
                FROM pratos p
                JOIN prato_ingredientes pi ON p.id = pi.prato_id
                JOIN ingredientes i ON pi.ingrediente_id = i.id
                WHERE p.bancada_id = ? AND i.quantidade_estoque >= pi.quantidade_necessaria
            """, (bancada_id,))
            rows = cursor.fetchall()
            return rows