import random
import string
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from app.middlewares.auth_middleware import admin_required
from app.models.bancada_model import Bancada
from app.models.pedido_model import Pedido
from app.models.ingrediente_model import Ingrediente
from app.database import DatabaseConnection

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

def gerar_id_aleatorio(prefixo):
    sufixo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"{prefixo}-{sufixo}"

@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    with DatabaseConnection() as cursor:
        # 1. Busca todas as bancadas cadastradas (para aparecer no select do cozinheiro)
        cursor.execute("SELECT id, nome, capacidade_mesas FROM bancadas")
        bancadas = cursor.fetchall()

        # 2. Busca todos os ingredientes cadastrados (para a aba de compras do admin)
        cursor.execute("SELECT id, nome, quantidade_estoque, preco FROM ingredientes")
        ingredientes = cursor.fetchall()

        # 3. Calcula o faturamento e gastos (opcional, mantendo a integridade financeira)
        cursor.execute("SELECT SUM(quantidade * preco_unitario) as total FROM itens_pedido")
        res_ganhos = cursor.fetchone()
        ganhos_totais = res_ganhos["total"] if res_ganhos and res_ganhos["total"] else 0.0

        cursor.execute("SELECT SUM(quantidade_estoque * preco) as total FROM ingredientes")
        res_gastos = cursor.fetchone()
        gastos_totais = res_gastos["total"] if res_gastos and res_gastos["total"] else 0.0

        cursor.execute("""
            SELECT p.id, 
                   COALESCE(c.nome, 'Não atribuído') as chef_nome,
                   p.tempo_limite,
                   CASE 
                       WHEN p.status = 'Entregue' AND p.tempo_real IS NOT NULL THEN p.tempo_real
                       WHEN p.status = 'Entregue' AND p.tempo_real IS NULL THEN CAST((julianday(p.atualizado_em) - julianday(p.criado_em)) * 1440 AS INTEGER)
                       ELSE CAST((julianday(DATETIME('now', 'localtime')) - julianday(p.criado_em)) * 1440 AS INTEGER)
                   END as tempo_decorrido,
                   p.status
            FROM pedidos p
            LEFT JOIN cozinheiros c ON p.cozinheiro_id = c.id
            ORDER BY p.id ASC
        """)
        relatorios_pedidos = cursor.fetchall()

        # 5. Nova consulta: Relaciona Bancadas e seus respectivos Cozinheiros
        cursor.execute("""
            SELECT b.id as bancada_id, b.nome as bancada_nome, b.capacidade_mesas,
                   c.id as chef_id, c.nome as chef_nome, c.turno
            FROM bancadas b
            LEFT JOIN cozinheiros c ON c.bancada_id = b.id
            ORDER BY b.nome ASC
        """)
        bancadas_com_chefs = cursor.fetchall()

    return render_template(
        "admin/dashboard.html", 
        bancadas=bancadas, 
        ingredientes=ingredientes, 
        relatorios=relatorios_pedidos,
        bancadas_com_chefs=bancadas_com_chefs,
        ganhos_totais=ganhos_totais,
        gastos_totais=gastos_totais
    )

@admin_bp.route("/bancada/nova", methods=["POST"])
@admin_required
def criar_bancada():
    nome = request.form.get("nome")
    capacidade = int(request.form.get("capacidade_mesas"))
    bancada_id = gerar_id_aleatorio("BAN")

    bancada = Bancada(id=bancada_id, nome=nome, capacidade_mesas=capacidade)
    bancada.save()

    # Cria automaticamente as mesas físicas da bancada no banco de dados
    with DatabaseConnection() as cursor:
        for i in range(1, capacidade + 1):
            cursor.execute("""
                INSERT INTO mesas (bancada_id, numero, status)
                VALUES (?, ?, 'livre')
            """, (bancada_id, i))

    flash(f"Bancada '{nome}' e suas {capacidade} mesas criadas com sucesso!", "success")
    return redirect(url_for("admin.dashboard"))

@admin_bp.route("/cozinheiro/novo", methods=["POST"])
@admin_required
def criar_cozinheiro():
    nome = request.form.get("nome").strip()
    turno = request.form.get("turno")  # 'manha', 'tarde', 'noite'
    bancada_id = request.form.get("bancada_id")
    cozinheiro_id = gerar_id_aleatorio("CHEF")  # Ex: CHEF-X7B2K

    # Nome de usuário para o login (pode ser o próprio nome)
    username_login = nome

    with DatabaseConnection() as cursor:
        # 1. Salva na tabela de cozinheiros
        cursor.execute("""
            INSERT INTO cozinheiros (id, nome, turno, bancada_id)
            VALUES (?, ?, ?, ?)
        """, (cozinheiro_id, nome, turno, bancada_id))

        # 2. Cria o usuário com Nome de Usuário = Nome e Senha = ID
        cursor.execute("""
            INSERT INTO usuarios (username, password, tipo)
            VALUES (?, ?, 'chef')
        """, (username_login, cozinheiro_id))

    flash(f"Cozinheiro(a) '{nome}' cadastrado(a)! Login: '{username_login}' | Senha/ID: '{cozinheiro_id}'", "success")
    return redirect(url_for("admin.dashboard"))

@admin_bp.route("/ingrediente/comprar", methods=["POST"])
@admin_required
def comprar_ingrediente():
    ingrediente_id = request.form.get("ingrediente_id")
    quantidade_comprada = int(request.form.get("quantidade"))

    with DatabaseConnection() as cursor:
        cursor.execute("SELECT nome, preco FROM ingredientes WHERE id = ?", (ingrediente_id,))
        ing = cursor.fetchone()

        if ing:
            custo_compra = quantidade_comprada * ing["preco"]
            
            # Atualiza a quantidade em estoque do ingrediente
            cursor.execute("""
                UPDATE ingredientes 
                SET quantidade_estoque = quantidade_estoque + ? 
                WHERE id = ?
            """, (quantidade_comprada, ingrediente_id))

            flash(f"Compra efetuada: {quantidade_comprada}x '{ing['nome']}' por R$ {custo_compra:.2f}!", "success")

    return redirect(url_for("admin.dashboard"))