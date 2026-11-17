from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from app.database import DatabaseConnection
from app.middlewares.auth_middleware import chef_required
from app.models.bancada_model import Bancada
from app.models.ingrediente_model import Ingrediente

chef_bp = Blueprint("chef", __name__, url_prefix="/chef")

@chef_bp.route("/kds")
@chef_required
def kds():
    username_logado = session.get("user")
    
    # Inicializamos variáveis vazias por segurança
    pedidos = []
    bancada_chef = None
    
    with DatabaseConnection() as cursor:
        # Descobre o ID do cozinheiro logado e sua bancada
        cursor.execute("""
            SELECT c.id, c.bancada_id, b.nome as bancada_nome 
            FROM cozinheiros c
            LEFT JOIN bancadas b ON c.bancada_id = b.id
            WHERE c.id = ? OR c.nome = ?
        """, (username_logado, username_logado))
        chef_info = cursor.fetchone()
        
        if chef_info:
            chef_id = chef_info["id"]
            
            if chef_info["bancada_id"]:
                bancada_chef = {
                    "id": chef_info["bancada_id"],
                    "bancada_nome": chef_info["bancada_nome"]
                }
            
            # Busca APENAS os pedidos ativos vinculados a este cozinheiro específico
            cursor.execute("""
                SELECT * FROM pedidos 
                WHERE cozinheiro_id = ? AND status != 'Entregue' 
                ORDER BY id ASC
            """, (chef_id,))
            pedidos = cursor.fetchall()

    return render_template("chef/kds.html", pedidos=pedidos, bancada_chef=bancada_chef)

@chef_bp.route("/pedido/<int:pedido_id>/status", methods=["POST"])
@chef_required
def atualizar_status(pedido_id):
    novo_status = request.form.get("status") # Recebido, Em preparo, Pronto, Entregue
    
    with DatabaseConnection() as cursor:
        if novo_status == "Entregue":
            # Salva o status, atualiza o timestamp e GRAVA DE VEZ o tempo_real decorrido em minutos
            cursor.execute("""
                UPDATE pedidos 
                SET status = ?, 
                    atualizado_em = DATETIME('now', 'localtime'),
                    tempo_real = CAST((julianday(DATETIME('now', 'localtime')) - julianday(criado_em)) * 1440 AS INTEGER)
                WHERE id = ?
            """, (novo_status, pedido_id))
        else:
            cursor.execute("""
                UPDATE pedidos 
                SET status = ?, atualizado_em = DATETIME('now', 'localtime') 
                WHERE id = ?
            """, (novo_status, pedido_id))

    flash(f"Status do pedido #{pedido_id} atualizado para '{novo_status}'.", "success")
    return redirect(url_for("chef.kds"))

@chef_bp.route("/prato/novo", methods=["GET", "POST"])
@chef_required
def novo_prato():
    username_logado = session.get("user")

    # 1. Descobre a bancada do cozinheiro logado logo de início
    with DatabaseConnection() as cursor:
        cursor.execute("""
            SELECT c.bancada_id, b.nome as bancada_nome 
            FROM cozinheiros c
            LEFT JOIN bancadas b ON c.bancada_id = b.id
            WHERE c.id = ? OR c.nome = ?
        """, (username_logado, username_logado))
        chef_bancada_info = cursor.fetchone()

    if request.method == "POST":
        nome_prato = request.form.get("nome")
        preco_prato = float(request.form.get("preco"))
        tempo_preparo = int(request.form.get("tempo_preparo"))
        foto_url = request.form.get("foto_url")
        
        # SEGURANÇA: Ignora qualquer bancada que venha do form e usa a bancada correta do chef logado
        if not chef_bancada_info or not chef_bancada_info["bancada_id"]:
            flash("Erro: Seu perfil não está vinculado a nenhuma bancada.", "danger")
            return redirect(url_for("chef.kds"))
            
        bancada_id = chef_bancada_info["bancada_id"]

        # Recebe os arrays vindos da tabela dinâmica do formulário
        nomes_ingredientes = request.form.getlist("ingrediente_nome[]")
        qtds_ingredientes = request.form.getlist("ingrediente_qtd[]")
        precos_ingredientes = request.form.getlist("ingrediente_preco[]")

        with DatabaseConnection() as cursor:
            # 1. Cria o Prato vinculado obrigatoriamente à bancada do chef
            cursor.execute("""
                INSERT INTO pratos (nome, preco, tempo_preparo, foto_url, bancada_id)
                VALUES (?, ?, ?, ?, ?)
            """, (nome_prato, preco_prato, tempo_preparo, foto_url, bancada_id))
            prato_id = cursor.lastrowid

            # 2. Processa cada ingrediente informado na tabela pelo Cozinheiro
            for i in range(len(nomes_ingredientes)):
                ing_nome = nomes_ingredientes[i].strip()
                ing_qtd = int(qtds_ingredientes[i])
                ing_preco = float(precos_ingredientes[i])

                # Verifica se o ingrediente já existe no banco
                cursor.execute("SELECT id FROM ingredientes WHERE LOWER(nome) = LOWER(?)", (ing_nome,))
                row = cursor.fetchone()

                if row:
                    ingrediente_id = row["id"]
                    cursor.execute("UPDATE ingredientes SET preco = ? WHERE id = ?", (ing_preco, ingrediente_id))
                else:
                    cursor.execute("""
                        INSERT INTO ingredientes (nome, quantidade_estoque, preco)
                        VALUES (?, 20, ?)
                    """, (ing_nome, ing_preco))
                    ingrediente_id = cursor.lastrowid

                # Associa o ingrediente ao prato
                cursor.execute("""
                    INSERT INTO prato_ingredientes (prato_id, ingrediente_id, quantidade_necessaria)
                    VALUES (?, ?, ?)
                """, (prato_id, ingrediente_id, ing_qtd))

        flash(f"Prato '{nome_prato}' cadastrado com sucesso na sua bancada ({chef_bancada_info['bancada_nome']})!", "success")
        return redirect(url_for("chef.kds"))

    return render_template("chef/novo_prato.html", bancada_chef=chef_bancada_info)

@chef_bp.route("/pratos/gerenciar")
@chef_required
def gerenciar_pratos():
    username_logado = session.get("user")

    with DatabaseConnection() as cursor:
        # Descobre a bancada do chef logado
        cursor.execute("""
            SELECT c.bancada_id, b.nome as bancada_nome 
            FROM cozinheiros c
            LEFT JOIN bancadas b ON c.bancada_id = b.id
            WHERE c.id = ? OR c.nome = ?
        """, (username_logado, username_logado))
        chef_info = cursor.fetchone()

        if not chef_info or not chef_info["bancada_id"]:
            pratos_bancada = []
        else:
            # Busca apenas os pratos pertencentes à bancada deste cozinheiro
            cursor.execute("""
                SELECT id, nome, preco, tempo_preparo 
                FROM pratos 
                WHERE bancada_id = ? 
                ORDER BY id DESC
            """, (chef_info["bancada_id"],))
            pratos_bancada = cursor.fetchall()

    return render_template("chef/gerenciar_pratos.html", pratos=pratos_bancada)

@chef_bp.route("/prato/<int:prato_id>/deletar", methods=["POST"])
@chef_required
def deletar_prato(prato_id):
    username_logado = session.get("user")

    with DatabaseConnection() as cursor:
        # 1. Descobre a bancada do chef logado
        cursor.execute("""
            SELECT bancada_id FROM cozinheiros 
            WHERE id = ? OR nome = ?
        """, (username_logado, username_logado))
        chef_info = cursor.fetchone()

        if not chef_info or not chef_info["bancada_id"]:
            flash("Erro de permissão.", "danger")
            return redirect(url_for("chef.kds"))

        bancada_chef_id = chef_info["bancada_id"]

        # 2. Verifica se o prato realmente pertence à bancada deste cozinheiro
        cursor.execute("SELECT id, nome, bancada_id FROM pratos WHERE id = ?", (prato_id,))
        prato = cursor.fetchone()

        if not prato or prato["bancada_id"] != bancada_chef_id:
            flash("Você não tem permissão para deletar este prato (ele pertence a outra bancada).", "danger")
            return redirect(url_for("chef.kds"))

        # 3. Deleta as relações de ingredientes do prato primeiro (evita erro de chave estrangeira)
        cursor.execute("DELETE FROM prato_ingredientes WHERE prato_id = ?", (prato_id,))

        # 4. Deleta o prato
        cursor.execute("DELETE FROM pratos WHERE id = ?", (prato_id,))

    flash(f"Prato '{prato['nome']}' excluído com sucesso da sua bancada!", "success")
    return redirect(url_for("chef.kds"))