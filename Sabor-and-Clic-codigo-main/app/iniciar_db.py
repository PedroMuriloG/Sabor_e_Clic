from database import DatabaseConnection
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()


with DatabaseConnection() as cursor:
    # 1. Usuários (Central de Autenticação e Login)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            tipo TEXT NOT NULL  -- 'admin', 'chef', 'cliente'
        )
    """)

    # 2. Bancadas (Espaços físicos)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bancadas (
            id TEXT PRIMARY KEY,  -- ID gerado aleatoriamente pelo admin
            nome TEXT UNIQUE NOT NULL,
            capacidade_mesas INTEGER NOT NULL
        )
    """)

    # 3. Cozinheiros (Vinculados a uma bancada e turno)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cozinheiros (
            id TEXT PRIMARY KEY,  -- ID aleatório gerado pelo sistema
            nome TEXT NOT NULL,
            turno TEXT NOT NULL,  -- 'manha', 'tarde', 'noite'
            bancada_id TEXT,
            FOREIGN KEY (bancada_id) REFERENCES bancadas(id)
        )
    """)

    # 4. Ingredientes (Controle de estoque, limite de 20 inicial)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ingredientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            quantidade_estoque INTEGER NOT NULL DEFAULT 20,
            preco REAL NOT NULL DEFAULT 0.0
        )
    """)

    # 5. Pratos (Vinculados a ingredientes e tempo de preparo)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pratos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            preco REAL NOT NULL,
            tempo_preparo INTEGER NOT NULL,  -- em minutos
            foto_url TEXT,
            bancada_id TEXT,
            FOREIGN KEY (bancada_id) REFERENCES bancadas(id)
        )
    """)

    # 5.1. Relação Prato <-> Ingredientes (Para saber quais ingredientes compõem o prato)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prato_ingredientes (
            prato_id INTEGER,
            ingrediente_id INTEGER,
            quantidade_necessaria INTEGER NOT NULL,
            FOREIGN KEY (prato_id) REFERENCES pratos(id),
            FOREIGN KEY (ingrediente_id) REFERENCES ingredientes(id)
        )
    """)

    # 6. Mesas (Vinculadas às bancadas)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mesas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero INTEGER NOT NULL,
            bancada_id TEXT,
            status TEXT DEFAULT 'livre',  -- 'livre', 'ocupada', 'reservada'
            liberacao_em TEXT,            -- Timer de 15 min após entrega
            FOREIGN KEY (bancada_id) REFERENCES bancadas(id)
        )
    """)

    # 7. Pedidos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_username TEXT NOT NULL,
            tipo_pedido TEXT NOT NULL,    -- 'entrega' ou 'presencial'
            endereco_entrega TEXT,
            mesa_id INTEGER,
            bancada_id TEXT,
            cozinheiro_id TEXT,
            status TEXT DEFAULT 'Recebido', -- 'Recebido' -> 'Em preparo' -> 'Pronto' -> 'Entregue'
            tempo_limite INTEGER,         -- Estabelecido pelo cozinheiro
            tempo_real INTEGER,           -- Calculado na entrega
            criado_em TEXT NOT NULL,
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (mesa_id) REFERENCES mesas(id),
            FOREIGN KEY (bancada_id) REFERENCES bancadas(id),
            FOREIGN KEY (cozinheiro_id) REFERENCES cozinheiros(id)
        )
    """)

    # 8. Itens do Pedido (A tabela ponte que você perguntou!)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS itens_pedido (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER,
            prato_id INTEGER,
            quantidade INTEGER NOT NULL,
            preco_unitario REAL NOT NULL,
            FOREIGN KEY (pedido_id) REFERENCES pedidos(id),
            FOREIGN KEY (prato_id) REFERENCES pratos(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reservas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_username TEXT NOT NULL,
            bancada_id TEXT,
            tipo_reserva TEXT NOT NULL, -- 'inteira' ou 'parcial'
            quantidade_mesas INTEGER NOT NULL,
            data_reserva TEXT NOT NULL, -- Novo: Armazena o dia (ex: 2026-06-06),
            hora_inicio TEXT NOT NULL,
            hora_fim TEXT NOT NULL,
            criado_em TEXT NOT NULL,
            FOREIGN KEY (bancada_id) REFERENCES bancadas(id)
        )
    """)

   # Pega a senha do .env (ajustado para aceitar ADMIN_PASSWORD ou ADMIN_senha)
    senha_admin = os.getenv('ADMIN_PASSWORD') or os.getenv('ADMIN_senha', 'admin123')
    senha_hash = generate_password_hash(senha_admin)

    # O parêntese da tupla (username, password, tipo) estava solto fora do execute
    cursor.execute("""
        INSERT OR IGNORE INTO usuarios (username, password, tipo)
        VALUES (?, ?, ?)
    """, ('admin', senha_hash, 'admin'))


print("Banco criado e Admin padrão inserido com sucesso!")