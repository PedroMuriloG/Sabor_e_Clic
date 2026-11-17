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

    with DatabaseConnection() as cursor:
        # 1. Enriquecer os itens do carrinho com a bancada e tempo de preparo de cada prato
        itens_com_detalhes = []
        bancadas_envolvidas = set()

        for item in itens_carrinho:
            prato_id = item["id"]
            preco = float(item["preco"])

            cursor.execute("SELECT bancada_id, tempo_preparo FROM pratos WHERE id = ?", (prato_id,))
            p_info = cursor.fetchone()
            if not p_info:
                continue
            
            bancada_id = p_info["bancada_id"]
            bancadas_envolvidas.add(bancada_id)

            itens_com_detalhes.append({
                "prato_id": prato_id,
                "quantidade": 1, # Se vier duplicado no array, podemos somar logo abaixo
                "preco_unitario": preco,
                "bancada_id": bancada_id,
                "tempo_preparo": p_info["tempo_preparo"]
            })

        # 2. Validação: Se nenhuma bancada foi envolvida (carrinho vazio ou pratos inválidos)
        if not bancadas_envolvidas:
            flash("Erro: Não foi possível identificar a bancada dos pratos selecionados.", "danger")
            return redirect(url_for("client.carrinho"))

        # Validação: Presencial NÃO pode misturar bancadas
        if len(bancadas_envolvidas) > 1 and tipo_pedido == "presencial":
            flash("Erro: Você não pode fazer um pedido presencial com pratos de bancadas diferentes ao mesmo tempo.", "danger")
            return redirect(url_for("client.carrinho"))

        # 3. VALIDAÇÃO DE MESA ATIVA EM OUTRA BANCADA (Apenas presencial)
        if tipo_pedido == "presencial":
            bancada_unica = list(bancadas_envolvidas)[0]
            cursor.execute("""
                SELECT DISTINCT bancada_id FROM pedidos 
                WHERE cliente_username = ? AND tipo_pedido = 'presencial' AND bancada_id != ?
                AND (
                    status != 'Entregue' 
                    OR (status = 'Entregue' AND (julianday(DATETIME('now', 'localtime')) - julianday(atualizado_em)) * 1440 < 15)
                )
            """, (cliente_username, bancada_unica))
            if cursor.fetchone():
                flash("Erro: Você já possui uma mesa ocupada ou em período de retenção em outra bancada!", "danger")
                return redirect(url_for("client.carrinho"))

        # 4. VALIDAÇÃO DE ESTOQUE GLOBAL ANTES DE DIVIDIR
        # Agrupa para somar quantidades caso o mesmo prato venha repetido
        agrupado_geral = {}
        for item in itens_com_detalhes:
            pid = item["prato_id"]
            if pid in agrupado_geral:
                agrupado_geral[pid]["quantidade"] += 1
            else:
                agrupado_geral[pid] = item.copy()

        for pid, dados in agrupado_geral.items():
            cursor.execute("""
                SELECT i.nome, i.quantidade_estoque, pi.quantidade_necessaria 
                FROM prato_ingredientes pi
                JOIN ingredientes i ON i.id = pi.ingrediente_id
                WHERE pi.prato_id = ?
            """, (pid,))
            ingredientes_prato = cursor.fetchall()

            for ing in ingredientes_prato:
                total_necessario = ing["quantidade_necessaria"] * dados["quantidade"]
                if ing["quantidade_estoque"] < total_necessario:
                    flash(f"Estoque insuficiente! O ingrediente '{ing['nome']}' tem apenas {ing['quantidade_estoque']} unidades.", "danger")
                    return redirect(url_for("client.carrinho"))

        # 5. SEPARAÇÃO E CRIAÇÃO DOS PEDIDOS POR BANCADA
        # Agrupa os itens do carrinho por bancada_id
        pedidos_por_bancada = {}
        for item in itens_com_detalhes:
            b_id = item["bancada_id"]
            if b_id not in pedidos_por_bancada:
                pedidos_por_bancada[b_id] = []
            pedidos_por_bancada[b_id].append(item)

        for bancada_id, itens_bancada in pedidos_por_bancada.items():
            # A. Encontra o cozinheiro disponível para esta bancada específica
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
                if cursor.fetchone()["total"] < 3:
                    cozinheiro_escolhido = chef_id
                    break

            if not cozinheiro_escolhido:
                flash(f"Capacidade esgotada na bancada de alguns dos pratos escolhidos.", "danger")
                return redirect(url_for("client.carrinho"))

            maior_tempo_preparo = max([i["tempo_preparo"] for i in itens_bancada], default=20)

                # Verificação de Reserva Ativa e Limite de Horário para Clientes com Reserva
            if tipo_pedido == "presencial":
                data_hoje = datetime.now().strftime("%Y-%m-%d")
                hora_atual = datetime.now().strftime("%H:%M")

                # 1. Verifica se o cliente possui uma reserva ativa para hoje e neste horário
                cursor.execute("""
                    SELECT id, hora_fim FROM reservas 
                    WHERE cliente_username = ? AND bancada_id = ? AND data_reserva = ?
                    AND hora_inicio <= ? AND hora_fim >= ?
                    LIMIT 1
                """, (cliente_username, bancada_id, data_hoje, hora_atual, hora_atual))
                reserva_ativa = cursor.fetchone()

                if reserva_ativa:
                    # Calcula o tempo total necessário (maior tempo de preparo + 15 min de retenção)
                    tempo_total_necessario = maior_tempo_preparo + 15
                    
                    # Converte horário atual e horário de término da reserva para minutos para comparar
                    h_atual, m_atual = map(int, hora_atual.split(":"))
                    minutos_atuais = h_atual * 60 + m_atual
                    
                    h_fim, m_fim = map(int, reserva_ativa["hora_fim"].split(":"))
                    minutos_fim_reserva = h_fim * 60 + m_fim

                    minutos_termino_estimado = minutos_atuais + tempo_total_necessario

                    # Se o pedido ultrapassar o horário limite da reserva
                    if minutos_termino_estimado > minutos_fim_reserva:
                        # Verifica se ainda há alguma mesa livre comum na bancada
                        cursor.execute("""
                            SELECT id FROM mesas 
                            WHERE bancada_id = ? AND status = 'livre' 
                            LIMIT 1
                        """, (bancada_id,))
                        mesa_livre_extra = cursor.fetchone()

                        if mesa_livre_extra:
                            # Se houver mesa livre, aloca para a mesa livre comum (com o fluxo normal de 15 min)
                            mesa_id = mesa_livre_extra["id"]
                            cursor.execute("UPDATE mesas SET status = 'ocupada' WHERE id = ?", (mesa_id,))
                            flash("Sua reserva está próxima do fim, mas você foi alocado para outra mesa disponível na bancada!", "info")
                        else:
                            # Se não houver mesa livre, o pedido passa a ser para viagem / delivery
                            tipo_pedido = "entrega" # ou altere para o status de viagem correspondente no seu sistema
                            mesa_id = None
                            flash("Sua reserva encerra em breve e não há mesas livres. Novos pedidos serão preparados apenas para viagem!", "warning")

            # B. Gerenciamento de Mesa (Se for presencial)
            mesa_id = None
            if tipo_pedido == "presencial":
                # Lógica da mesa única...
                cursor.execute("""
                    SELECT p.mesa_id FROM pedidos p
                    WHERE p.cliente_username = ? AND p.bancada_id = ? AND p.mesa_id IS NOT NULL
                    AND (p.status != 'Entregue' OR (p.status = 'Entregue' AND (julianday(DATETIME('now', 'localtime')) - julianday(p.atualizado_em)) * 1440 < 15))
                    ORDER BY p.id DESC LIMIT 1
                """, (cliente_username, bancada_id))
                mesa_existente = cursor.fetchone()

                if mesa_existente:
                    mesa_id = mesa_existente["mesa_id"]
                else:
                    cursor.execute("SELECT id FROM mesas WHERE bancada_id = ? AND status = 'livre' LIMIT 1", (bancada_id,))
                    m_info = cursor.fetchone()
                    if not m_info:
                        flash("Sem mesas livres nesta bancada.", "danger")
                        return redirect(url_for("client.carrinho"))
                    mesa_id = m_info["id"]
                    cursor.execute("UPDATE mesas SET status = 'ocupada' WHERE id = ?", (mesa_id,))

            # C. Calcula o maior tempo de preparo específico desta bancada
            maior_tempo = max([i["tempo_preparo"] for i in itens_bancada], default=20)

            # D. Consolida os itens repetidos dentro da mesma bancada
            itens_agrupados_bancada = {}
            for item in itens_bancada:
                pid = item["prato_id"]
                if pid in itens_agrupados_bancada:
                    itens_agrupados_bancada[pid]["quantidade"] += 1
                else:
                    itens_agrupados_bancada[pid] = {
                        "prato_id": pid,
                        "quantidade": item["quantidade"],
                        "preco_unitario": item["preco_unitario"]
                    }
            
            lista_final_bancada = list(itens_agrupados_bancada.values())

            # E. Salva o pedido independente para esta bancada
            novo_pedido = Pedido(
                cliente_username=cliente_username,
                tipo_pedido=tipo_pedido,
                endereco_entrega=endereco_entrega,
                mesa_id=mesa_id,
                bancada_id=bancada_id,
                tempo_limite=maior_tempo
            )
            novo_pedido.cozinheiro_id = cozinheiro_escolhido
            novo_pedido.save_with_items(lista_final_bancada)

    flash("Pedidos realizados com sucesso! Caso tenha itens de cozinhas diferentes no delivery, eles foram divididos para cada bancada correspondente.", "success")
    return redirect(url_for("client.carrinho"))

@client_bp.route("/reservar-bancada", methods=["GET", "POST"])
@client_required
def reservar_bancada():
    cliente_username = session.get("user")

    with DatabaseConnection() as cursor:
        if request.method == "POST":
            bancada_id = request.form.get("bancada_id")
            tipo_reserva = request.form.get("tipo_reserva")  # 'inteira' ou 'parcial'
            qtd_mesas_desejada = int(request.form.get("quantidade_mesas", 1))
            data_reserva = request.form.get("data_reserva")  # YYYY-MM-DD
            hora_inicio = request.form.get("hora_inicio")    # HH:MM
            hora_fim = request.form.get("hora_fim")          # HH:MM

            # 1. Pega capacidade total da bancada
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

            # 2. VERIFICAÇÃO DE CONFLITO DE HORÁRIO E MESAS NO MESMO DIA
            # Duas reservas se sobrepõem no mesmo dia se: (InicioA < FimB) e (FimA > InicioB)
            cursor.execute("""
                SELECT SUM(quantidade_mesas) as total_reservado 
                FROM reservas 
                WHERE bancada_id = ? AND data_reserva = ? 
                AND (hora_inicio < ? AND hora_fim > ?)
            """, (bancada_id, data_reserva, hora_fim, hora_inicio))
            res_conflito = cursor.fetchone()
            mesas_ja_reservadas = res_conflito["total_reservado"] if res_conflito and res_conflito["total_reservado"] else 0

            mesas_livres_no_horario = capacidade_total - mesas_ja_reservadas

            if quantidade_para_reservar > mesas_livres_no_horario:
                flash(f"Não há mesas suficientes neste horário! Restam apenas {mesas_livres_no_horario} mesa(s) livres na bancada para o dia {data_reserva} entre {hora_inicio} e {hora_fim}. Escolha outro horário ou dia.", "warning")
                return redirect(url_for("client.reservar_bancada"))

            # 3. Salva a reserva se houver disponibilidade
            cursor.execute("""
                INSERT INTO reservas (cliente_username, bancada_id, tipo_reserva, quantidade_mesas, data_reserva, hora_inicio, hora_fim, criado_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, DATETIME('now', 'localtime'))
            """, (cliente_username, bancada_id, tipo_reserva, quantidade_para_reservar, data_reserva, hora_inicio, hora_fim))

            flash(f"Reserva realizada com sucesso para o dia {data_reserva} das {hora_inicio} às {hora_fim}!", "success")
            return redirect(url_for("client.reservar_bancada"))

        # Busca as bancadas para o formulário
        bancadas = Bancada.get_all()

        # Busca as reservas do próprio cliente para exibir na tabela acima
        cursor.execute("""
            SELECT r.id, b.nome as bancada_nome, r.tipo_reserva, r.quantidade_mesas, r.data_reserva, r.hora_inicio, r.hora_fim
            FROM reservas r
            JOIN bancadas b ON b.id = r.bancada_id
            WHERE r.cliente_username = ?
            ORDER BY r.data_reserva DESC, r.hora_inicio DESC
        """, (cliente_username,))
        minhas_reservas = cursor.fetchall()

    return render_template("client/reservar_bancada.html", bancadas=bancadas, minhas_reservas=minhas_reservas)