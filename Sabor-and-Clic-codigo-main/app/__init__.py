from flask import Flask

def create_app():
  app = Flask(
      __name__, template_folder="views/templates", static_folder="views/static"
  )

  @app.after_request
  def add_header(response):
    # Impede que o navegador armazene páginas protegidas em cache
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

  import os
  from dotenv import load_dotenv

  load_dotenv()
  app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "chave_padrao_para_desenvolvimento")
  #com o os.getenv, a chave é guardada no .env (que fica no .gitignore)

  #registrar blueprints
  from app.controllers.auth_controller import auth_bp
  from app.controllers.admin_controller import admin_bp
  from app.controllers.chef_controller import chef_bp
  from app.controllers.client_controller import client_bp
  from app.controllers.main_controller import main_bp

  app.register_blueprint(main_bp)
  app.register_blueprint(auth_bp)
  app.register_blueprint(admin_bp)
  app.register_blueprint(chef_bp)
  app.register_blueprint(client_bp)

  return app