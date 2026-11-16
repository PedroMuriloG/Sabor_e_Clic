import json
from datetime import datetime
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from app.middlewares.auth_middleware import client_required
from app.models.bancada_model import Bancada
from app.models.prato_model import Prato
from app.models.pedido_model import Pedido
from app.database import DatabaseConnection

client_bp = Blueprint("client", __name__, url_prefix="/cliente")

def obter_turno_atual():
    hora = datetime.now().hour
    if 6 <= hora < 12:
        return "manha"
    elif 12 <= hora < 18:
        return "tarde"
    else:
        return "noite"

@client_bp.route("/catalogo")
@client_required
def catalogo():
    turno_atual = obter_turno_atual()
    
    with DatabaseConnection() as cursor:
        # Busca todas as bancadas e verifica quais têm capacidade (cozinheiros com menos de 3 pedidos ativos)
        cursor.execute("""
            SELECT DISTINCT b.id, b.nome, b.capacidade_mesas
            FROM bancadas b
            JOIN cozinheiros c ON c.bancada_id = b.id
            WHERE c.turno = ?
        """, (turno_atual,))
        bancadas_cadastradas = cursor.fetchall()

    bancadas_disponiveis = []
    
    with DatabaseConnection() as cursor:
        for bancada in bancadas_cadastradas:
            bancada_id = bancada["id"]
            
            # Pega todos os cozinheiros desta bancada no turno atual ordenados por ordem de cadastro (prioridade)
            cursor.execute("""
                SELECT id FROM cozinheiros 
                WHERE bancada_id = ? AND turno = ? 
                ORDER BY id ASC
            """, (bancada_id, turno_atual))
            cozinheiros = cursor.fetchall()
            
            # Verifica se pelo menos um cozinheiro tem menos de 3 pedidos ativos
            tem_vaga = False
            for chef in cozinheiros:
                chef_id = chef["id"]
                cursor.execute("""
                    SELECT COUNT(*) as total 
                    FROM pedidos 
                    WHERE cozinheiro_id = ? AND status != 'Entregue'
                """, (chef_id,))
                pedidos_ativos = cursor.fetchone()["total"]
                
                if pedidos_ativos < 3:
                    tem_vaga = True
                    break # Encontrou um cozinheiro livre/com vaga
            
            if tem_vaga:
                bancadas_disponiveis.append(bancada)

    return render_template("client/catalogo.html", bancadas=bancadas_disponiveis, turno_atual=turno_atual)

@client_bp.route("/bancada/<bancada_id>/pratos")
@client_required
def pratos_bancada(bancada_id):
    turno_atual = obter_turno_atual()
    
    # Valida se ainda há vagas nos cozinheiros da bancada
    with DatabaseConnection() as cursor:
        cursor.execute("""
            SELECT id FROM cozinheiros 
            WHERE bancada_id = ? AND turno = ? 
            ORDER BY id ASC
        """, (bancada_id, turno_atual))
        cozinheiros = cursor.fetchall()

        vaga_encontrada = False
        for chef in cozinheiros:
            cursor.execute("""
                SELECT COUNT(*) as total 
                FROM pedidos 
                WHERE cozinheiro_id = ? AND status != 'Entregue'
            """, (chef["id"],))
            if cursor.fetchone()["total"] < 3:
                vaga_encontrada = True
                break

        if not vaga_encontrada:
            flash("Todos os cozinheiros desta bancada atingiram o limite de 3 pedidos ativos no momento.", "warning")
            return redirect(url_for("client.catalogo"))

    pratos = Prato.get_disponiveis_por_bancada(bancada_id)
    return render_template("client/pratos.html", pratos=pratos, bancada_id=bancada_id)

@client_bp.route("/carrinho")
@client_required
def carrinho():
    cliente_username = session.get("user")

    with DatabaseConnection() as cursor:
        cursor.execute("""
            SELECT id, tipo_pedido, status, tempo_limite, criado_em 
            FROM pedidos 
            WHERE cliente_username = ? 
            ORDER BY id DESC
        """, (cliente_username,))
        meus_pedidos = cursor.fetchall()

    return render_template("client/carrinho.html", meus_pedidos=meus_pedidos)

@client_bp.route("/pedido/finalizar", methods=["POST"])
@client_required
def finalizar_pedido():
    cliente_username = session.get("user")
    tipo_pedido = request.form.get("tipo_pedido", "presencial")
    endereco_entrega = request.form.get("endereco_entrega") if tipo_pedido == "entrega" else ""
    cart_data_json = request.form.get("cart_data")

    if not cart_data_json:
        flash("O seu carrinho está vazio ou os dados não foram enviados.", "warning")
        return redirect(url_for("client.carrinho"))

    try:
        itens_carrinho = json.loads(cart_data_json)
    except Exception:
        flash("Erro ao processar os itens do carrinho.", "danger")
        return redirect(url_for("client.carrinho"))

    if not itens_carrinho:
        flash("Adicione pelo menos um item ao carrinho.", "warning")
        return redirect(url_for("client.carrinho"))

    turno_atual = obter_turno_atual()
    primeiro_prato_id = itens_carrinho[0]["id"]

    # Agrupa os itens e soma quantidades do carrinho
    itens_agrupados = {}
    for item in itens_carrinho:
        prato_id = item["id"]
        preco = float(item["preco"])
        if prato_id in itens_agrupados:
            itens_agrupados[prato_id]["quantidade"] += 1
        else:
            itens_agrupados[prato_id] = {
                "prato_id": prato_id,
                "quantidade": 1,
                "preco_unitario": preco
            }

    lista_items = list(itens_agrupados.values())

    with DatabaseConnection() as cursor:
        # 1. VALIDAÇÃO DE ESTOQUE: Verifica se algum ingrediente ficará negativo
        for item in lista_items:
            cursor.execute("""
                SELECT i.id, i.nome, i.quantidade_estoque, pi.quantidade_necessaria 
                FROM prato_ingredientes pi
                JOIN ingredientes i ON i.id = pi.ingrediente_id
                WHERE pi.prato_id = ?
            """, (item["prato_id"],))
            ingredientes_prato = cursor.fetchall()

            for ing in ingredientes_prato:
                total_necessario = ing["quantidade_necessaria"] * item["quantidade"]
                if ing["quantidade_estoque"] < total_necessario:
                    flash(f"Estoque insuficiente! O ingrediente '{ing['nome']}' tem apenas {ing['quantidade_estoque']} unidades, mas este prato precisa de {total_necessario}.", "danger")
                    return redirect(url_for("client.carrinho"))

        # 2. Descobre a bancada do prato
        cursor.execute("SELECT bancada_id FROM pratos WHERE id = ?", (primeiro_prato_id,))
        prato_info = cursor.fetchone()
        if not prato_info:
            flash("Erro ao identificar a bancada do prato.", "danger")
            return redirect(url_for("client.carrinho"))
        bancada_id = prato_info["bancada_id"]

        # 3. Distribuição por fila de prioridade (Máx 3 pedidos por cozinheiro)
        cursor.execute("""
            SELECT id FROM cozinheiros 
            WHERE bancada_id = ? AND turno = ? 
            ORDER BY id ASC
        """, (bancada_id, turno_atual))
        cozinheiros = cursor.fetchall()

        cozinheiro_escolhido = None
        for chef in cozinheiros:
            chef_id = chef["id"]
            cursor.execute("""
                SELECT COUNT(*) as total 
                FROM pedidos 
                WHERE cozinheiro_id = ? AND status != 'Entregue'
            """, (chef_id,))
            pedidos_ativos = cursor.fetchone()["total"]

            if pedidos_ativos < 3:
                cozinheiro_escolhido = chef_id
                break

        if not cozinheiro_escolhido:
            flash("Capacidade esgotada: todos os cozinheiros desta bancada estão com 3 pedidos ativos.", "danger")
            return redirect(url_for("client.carrinho"))

        # 4. VALIDAÇÃO DE MESAS (Reutiliza mesa ativa do cliente ou pega uma livre)
        mesa_id = None
        if tipo_pedido == "presencial":
            # Primeiro, libera automaticamente no banco as mesas cujos últimos pedidos entregues já passaram de 15 minutos
            cursor.execute("""
                UPDATE mesas 
                SET status = 'livre' 
                WHERE bancada_id = ? AND status = 'ocupada' AND id NOT IN (
                    SELECT DISTINCT p.mesa_id FROM pedidos p
                    WHERE p.mesa_id IS NOT NULL 
                    AND p.status = 'Entregue'
                    AND (julianday(DATETIME('now', 'localtime')) - julianday(p.atualizado_em)) * 1440 < 15
                ) AND id NOT IN (
                    SELECT DISTINCT p.mesa_id FROM pedidos p
                    WHERE p.mesa_id IS NOT NULL 
                    AND p.status != 'Entregue'
                )
            """, (bancada_id,))

            # Verifica se o cliente JÁ possui uma mesa ativa ou recente nesta bancada (mesmo que o último pedido já tenha sido entregue há menos de 15 min)
            cursor.execute("""
                SELECT p.mesa_id FROM pedidos p
                WHERE p.cliente_username = ? AND p.bancada_id = ? AND p.mesa_id IS NOT NULL
                AND (
                    p.status != 'Entregue' 
                    OR (p.status = 'Entregue' AND (julianday(DATETIME('now', 'localtime')) - julianday(p.atualizado_em)) * 1440 < 15)
                )
                ORDER BY p.id DESC
                LIMIT 1
            """, (cliente_username, bancada_id))
            mesa_existente = cursor.fetchone()

            if mesa_existente:
                # Reutiliza a mesma mesa em que o cliente já está!
                mesa_id = mesa_existente["mesa_id"]
            else:
                # Se não tem mesa ativa, busca a capacidade máxima da bancada
                cursor.execute("SELECT capacidade_mesas FROM bancadas WHERE id = ?", (bancada_id,))
                bancada_info = cursor.fetchone()
                capacidade_maxima = bancada_info["capacidade_mesas"] if bancada_info else 0

                # Conta quantas mesas estão ocupadas no momento
                cursor.execute("""
                    SELECT COUNT(DISTINCT m.id) as total 
                    FROM mesas m
                    JOIN pedidos p ON p.mesa_id = m.id
                    WHERE m.bancada_id = ? AND (
                        p.status != 'Entregue' 
                        OR (p.status = 'Entregue' AND (julianday(DATETIME('now', 'localtime')) - julianday(p.atualizado_em)) * 1440 < 15)
                    )
                """, (bancada_id,))
                total_ocupadas = cursor.fetchone()["total"]

                if total_ocupadas >= capacidade_maxima:
                    flash(f"Todas as {capacidade_maxima} mesas desta bancada estão ocupadas no momento! Escolha a opção de Delivery.", "danger")
                    return redirect(url_for("client.carrinho"))
                
                # Pega a primeira mesa livre disponível
                cursor.execute("""
                    SELECT id FROM mesas 
                    WHERE bancada_id = ? AND status = 'livre' 
                    LIMIT 1
                """, (bancada_id,))
                mesa_info = cursor.fetchone()

                if not mesa_info:
                    flash("Não há mesas livres no momento. Selecione Delivery.", "danger")
                    return redirect(url_for("client.carrinho"))
                
                mesa_id = mesa_info["id"]

            # Garante que a mesa fique marcada como ocupada
            cursor.execute("UPDATE mesas SET status = 'ocupada' WHERE id = ?", (mesa_id,))

        # 5. Calcula o tempo limite do pedido com base nos pratos
        maior_tempo_preparo = 0
        for item in itens_carrinho:
            cursor.execute("SELECT tempo_preparo FROM pratos WHERE id = ?", (item["id"],))
            p_info = cursor.fetchone()
            if p_info and p_info["tempo_preparo"] > maior_tempo_preparo:
                maior_tempo_preparo = p_info["tempo_preparo"]

    # Cria o pedido e vincula o cozinheiro
    novo_pedido = Pedido(
        cliente_username=cliente_username,
        tipo_pedido=tipo_pedido,
        endereco_entrega=endereco_entrega,
        mesa_id=mesa_id,
        bancada_id=bancada_id,
        tempo_limite=maior_tempo_preparo if maior_tempo_preparo > 0 else 20
    )
    novo_pedido.cozinheiro_id = cozinheiro_escolhido

    try:
        novo_pedido.save_with_items(lista_items)
        flash(f"Pedido realizado com sucesso! Direcionado ao cozinheiro da fila.", "success")
    except Exception:
        flash("Erro ao finalizar pedido.", "danger")

    return redirect(url_for("client.carrinho"))

@client_bp.route("/reservar-bancada", methods=["GET", "POST"])
@client_required
def reservar_bancada():
    cliente_username = session.get("user")

    if request.method == "POST":
        bancada_id = request.form.get("bancada_id")
        tipo_reserva = request.form.get("tipo_reserva")  # 'inteira' ou 'parcial'
        qtd_mesas_desejada = int(request.form.get("quantidade_mesas", 1))
        data_reserva = request.form.get("data_reserva")  # Data escolhida pelo cliente
        hora_inicio = request.form.get("hora_inicio")
        hora_fim = request.form.get("hora_fim")

        with DatabaseConnection() as cursor:
            # Pega capacidade total da bancada
            cursor.execute("SELECT capacidade_mesas FROM bancadas WHERE id = ?", (bancada_id,))
            b_info = cursor.fetchone()
            if not b_info:
                flash("Bancada não encontrada.", "danger")
                return redirect(url_for("client.reservar_bancada"))
            
            capacidade_total = b_info["capacidade_mesas"]

            if tipo_reserva == "inteira":
                quantidade_para_reservar = capacidade_total
            else:
                quantidade_para_reservar = qtd_mesas_desejada
                if quantidade_para_reservar > capacidade_total:
                    flash(f"A quantidade excede a capacidade máxima da bancada ({capacidade_total} mesas).", "danger")
                    return redirect(url_for("client.reservar_bancada"))

            # Salva a reserva incluindo a data
            cursor.execute("""
                INSERT INTO reservas (cliente_username, bancada_id, tipo_reserva, quantidade_mesas, data_reserva, hora_inicio, hora_fim, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, DATETIME('now', 'localtime'))
            """, (cliente_username, bancada_id, tipo_reserva, quantidade_para_reservar, data_reserva, hora_inicio, hora_fim))

            flash(f"Reserva realizada com sucesso para o dia {data_reserva} das {hora_inicio} até às {hora_fim}!", "success")
            return redirect(url_for("client.catalogo"))

    bancadas = Bancada.get_all()
    return render_template("client/reservar_bancada.html", bancadas=bancadas)