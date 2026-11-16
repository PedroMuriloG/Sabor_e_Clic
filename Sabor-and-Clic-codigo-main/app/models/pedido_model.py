from app.database import DatabaseConnection
from datetime import datetime

class Pedido:
    def __init__(self, cliente_username, tipo_pedido, endereco_entrega, mesa_id, bancada_id, tempo_limite, id=None, status="Recebido", cozinheiro_id=None):
        self.id = id
        self.cliente_username = cliente_username
        self.tipo_pedido = tipo_pedido
        self.endereco_entrega = endereco_entrega
        self.mesa_id = mesa_id
        self.bancada_id = bancada_id
        self.cozinheiro_id = cozinheiro_id
        self.status = status
        self.tempo_limite = tempo_limite
        self.criado_em = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def save_with_items(self, lista_itens):
        with DatabaseConnection() as cursor:
            # 1. Insere o pedido principal salvando o cozinheiro_id
            cursor.execute("""
                INSERT INTO pedidos (
                    cliente_username, tipo_pedido, endereco_entrega, 
                    mesa_id, bancada_id, cozinheiro_id, status, 
                    tempo_limite, criado_em
                ) VALUES (?, ?, ?, ?, ?, ?, 'Recebido', ?, ?)
            """, (
                self.cliente_username, 
                self.tipo_pedido, 
                self.endereco_entrega, 
                self.mesa_id, 
                self.bancada_id, 
                self.cozinheiro_id,  # <--- Inserindo no banco
                self.tempo_limite, 
                self.criado_em
            ))
            
            pedido_id = cursor.lastrowid

            # 2. Insere os itens do pedido e desconta do estoque
            for item in lista_itens:
                cursor.execute("""
                    INSERT INTO itens_pedido (pedido_id, prato_id, quantidade, preco_unitario)
                    VALUES (?, ?, ?, ?)
                """, (pedido_id, item["prato_id"], item["quantidade"], item["preco_unitario"]))

                # Desconta do estoque de ingredientes do prato
                cursor.execute("""
                    UPDATE ingredientes 
                    SET quantidade_estoque = quantidade_estoque - (pi.quantidade_necessaria * ?)
                    FROM prato_ingredientes pi
                    WHERE pi.prato_id = ? AND ingredientes.id = pi.ingrediente_id
                """, (item["quantidade"], item["prato_id"]))
            
            return pedido_id

    @staticmethod
    def get_relatorio_geral():
        """Retorna dados para o painel do Admin (faturamento, entregues, atrasos, bancada/cozinheiro)"""
        with DatabaseConnection() as cursor:
            cursor.execute("""
                SELECT p.id, p.status, p.tempo_limite, p.tempo_real, b.nome as bancada_nome,
                       c.nome as cozinheiro_nome
                FROM pedidos p
                LEFT JOIN bancadas b ON p.bancada_id = b.id
                LEFT JOIN cozinheiros c ON c.bancada_id = b.id
            """)
            return cursor.fetchall()