from flask import Flask
from .config import Config
from .extensions import db, login_manager


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    login_manager.init_app(app)

    from . import models  # registra i modelli
    from .auth.routes import auth_bp
    from .dashboard.routes import dashboard_bp
    from .work.routes import work_bp
    from .quality.routes import quality_bp
    from .maintenance.routes import maintenance_bp
    from .safety.routes import safety_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(work_bp)
    app.register_blueprint(quality_bp)
    app.register_blueprint(maintenance_bp)
    app.register_blueprint(safety_bp)

    with app.app_context():
        db.create_all()

    return app
