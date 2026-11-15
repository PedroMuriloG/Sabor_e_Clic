from functools import wraps
from flask import flash, redirect, session, url_for

def guest_required(f):
    """Garante que apenas visitantes (não logados) acessem a rota (ex: login e register)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" in session:
            tipo = session.get("tipo")
            if tipo == "admin":
                return redirect(url_for("admin.dashboard"))
            elif tipo == "chef":
                return redirect(url_for("chef.kds"))
            else:
                return redirect(url_for("client.catalogo"))
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
  @wraps(f)
  def decorated_function(*args, **kwargs):
    if "user" not in session:
      flash("Por favor, faça login para acessar esta página.", "warning")
      return redirect(url_for("auth.login"))
    return f(*args, **kwargs)

  return decorated_function


def admin_required(f):
  @wraps(f)
  def decorated_function(*args, **kwargs):
    if session.get("tipo") != "admin":
      flash("Acesso restrito a administradores.", "danger")
      return redirect(url_for("auth.login"))
    return f(*args, **kwargs)

  return decorated_function


def chef_required(f):
  @wraps(f)
  def decorated_function(*args, **kwargs):
    if session.get("tipo") != "chef":
      flash("Acesso restrito a cozinheiros.", "danger")
      return redirect(url_for("auth.login"))
    return f(*args, **kwargs)

  return decorated_function


def client_required(f):
  @wraps(f)
  def decorated_function(*args, **kwargs):
    if session.get("tipo") != "cliente":
      flash("Acesso restrito a clientes.", "danger")
      return redirect(url_for("auth.login"))
    return f(*args, **kwargs)

  return decorated_function