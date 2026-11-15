from app.database import DatabaseConnection

class Bancada:
    def __init__(self, id, nome, capacidade_mesas):
        self.id = id
        self.nome = nome
        self.capacidade_mesas = capacidade_mesas

    @staticmethod
    def get_all():
        with DatabaseConnection() as cursor:
            cursor.execute("SELECT id, nome, capacidade_mesas FROM bancadas")
            rows = cursor.fetchall()
            return [Bancada(id=row["id"], nome=row["nome"], capacidade_mesas=row["capacidade_mesas"]) for row in rows]

    @staticmethod
    def get_by_id(bancada_id):
        with DatabaseConnection() as cursor:
            cursor.execute("SELECT id, nome, capacidade_mesas FROM bancadas WHERE id = ?", (bancada_id,))
            row = cursor.fetchone()
            if row:
                return Bancada(id=row["id"], nome=row["nome"], capacidade_mesas=row["capacidade_mesas"])
            return None

    def save(self):
        with DatabaseConnection() as cursor:
            cursor.execute(
                "INSERT INTO bancadas (id, nome, capacidade_mesas) VALUES (?, ?, ?)",
                (self.id, self.nome, self.capacidade_mesas)
            )
            
            # Cria automaticamente as mesas associadas a esta bancada
            for num in range(1, self.capacidade_mesas + 1):
                cursor.execute(
                    "INSERT INTO mesas (numero, bancada_id, status) VALUES (?, ?, 'livre')",
                    (num, self.id)
                )