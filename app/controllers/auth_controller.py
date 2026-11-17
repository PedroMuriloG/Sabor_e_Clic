from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from app.middlewares.auth_middleware import guest_required, login_required
from app.models.user_model import Usuario
from werkzeug.security import check_password_hash, generate_password_hash
from app.database import DatabaseConnection

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
@guest_required
def login():
  if request.method == "POST":
    identificador = request.form.get("username") # Pode ser o e-mail do cliente ou o ID do chef
    password = request.form.get("password")

    with DatabaseConnection() as cursor:
        # Busca pelo e-mail (cliente) ou username/ID (chef/admin)
        cursor.execute("SELECT * FROM usuarios WHERE email = ? OR username = ?", (identificador, identificador))
        row = cursor.fetchone()

    user = None
    if row:
        user = Usuario(id=row["id"], username=row["username"], password=row["password"], tipo=row["tipo"])

    if user and check_password_hash(user.password, password):
      session["user"] = user.username # Nome do usuário para exibir na tela
      session["tipo"] = user.tipo

      flash(f"Bem-vindo(a), {user.username}!", "success")

      if user.tipo == "admin":
        return redirect(url_for("admin.dashboard"))
      elif user.tipo == "chef":
        return redirect(url_for("chef.kds"))
      else:
        return redirect(url_for("client.catalogo"))
    else:
      flash("E-mail/Usuário ou senha incorretos.", "danger")

  return render_template("login.html")

@auth_bp.route("/register", methods=["GET", "POST"])
@guest_required
def register():
    """Cadastro exclusivo para novos Clientes"""
    if request.method == "POST":
        username = request.form.get("nome")
        email = request.form.get("email").strip().lower()
        data_nascimento = request.form.get("data_nascimento")
        password = request.form.get("password")

        with DatabaseConnection() as cursor:
            # Verifica se o e-mail já existe
            cursor.execute("SELECT id FROM usuarios WHERE email = ?", (email,))
            if cursor.fetchone():
                flash("Este e-mail já está cadastrado.", "warning")
                return redirect(url_for("auth.register"))

            # Cria o hash seguro da senha
            senha_hash = generate_password_hash(password)

            # Insere salvando tanto o nome quanto repetindo no username para satisfazer a constraint do banco
            cursor.execute("""
                INSERT INTO usuarios (username, email, data_nascimento, password, tipo)
                VALUES (?, ?, ?, ?, 'cliente')
            """, (username, email, data_nascimento, senha_hash))

        flash("Cadastro realizado com sucesso! Faça login com seu nome ou e-mail.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")

@auth_bp.route("/logout")
@login_required
def logout():
  session.clear()
  flash("Você saiu da conta.", "info")
  return redirect(url_for("auth.login"))