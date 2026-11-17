from app.database import DatabaseConnection

class Usuario:
    def __init__(self, username, password, tipo, id=None):
        self.id = id
        self.username = username
        self.password = password
        self.tipo = tipo  # 'admin', 'chef', 'cliente'

    @staticmethod
    def get_by_username(username):
        with DatabaseConnection() as cursor:
            cursor.execute(
                "SELECT id, username, password, tipo FROM usuarios WHERE username = ?",
                (username,)
            )
            row = cursor.fetchone()
            if row:
                return Usuario(
                    username=row["username"],
                    password=row["password"],
                    tipo=row["tipo"],
                    id=row["id"]
                )
            return None

    def save(self):
        with DatabaseConnection() as cursor:
            cursor.execute(
                "INSERT INTO usuarios (username, password, tipo) VALUES (?, ?, ?)",
                (self.username, self.password, self.tipo)
            )