from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from app.middlewares.auth_middleware import guest_required, login_required
from app.models.user_model import Usuario
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
@guest_required
def login():
  if request.method == "POST":
    username = request.form.get("username")
    password = request.form.get("password")

    # Busca o usuário pelo username no banco
    user = Usuario.get_by_username(username)
    # Usa check_password_hash para comparar a senha digitada com o hash do banco
    if user and check_password_hash(user.password, password):
      # Guarda os dados principais da sessão
      session["user"] = user.username
      session["tipo"] = user.tipo

      flash(f"Bem-vindo(a), {user.username}!", "success")

      # Redirecionamento dinâmico conforme o tipo de usuário
      if user.tipo == "admin":
        return redirect(url_for("admin.dashboard"))
      elif user.tipo == "chef":
        return redirect(url_for("chef.kds"))
      else:
        return redirect(url_for("client.catalogo"))
    else:
      flash("Usuário ou senha incorretos.", "danger")

  return render_template("login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
@guest_required
def register():
    """Cadastro exclusivo para novos Clientes"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Verifica se já existe
        if Usuario.get_by_username(username):
            flash("Este usuário já existe.", "warning")
            return redirect(url_for("auth.register"))

        # Cria o hash seguro da senha antes de salvar
        senha_hash = generate_password_hash(password)

        # Cadastra o novo usuário obrigatoriamente com o tipo 'cliente' e a senha criptografada
        novo_usuario = Usuario(
            username=username, password=senha_hash, tipo="cliente"
        )
        novo_usuario.save()

        flash("Cadastro de cliente realizado com sucesso! Faça login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")

@auth_bp.route("/logout")
@login_required
def logout():
  session.clear()
  flash("Você saiu da conta.", "info")
  return redirect(url_for("auth.login"))