from flask import Flask
from .config import Config
from .extensions import db, login_manager


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    login_manager.init_app(app)

    from . import models  # registra i modelli
    from . import models_sa8000  # registra i modelli SA8000
    from . import models_environment  # registra i modelli ambientali (ISO 14001)
    from . import models_esg  # registra i modelli ESG
    from . import models_library  # registra il modello delle compilazioni paperless
    from .auth.routes import auth_bp
    from .dashboard.routes import dashboard_bp
    from .work.routes import work_bp
    from .quality.routes import quality_bp
    from .maintenance.routes import maintenance_bp
    from .safety.routes import safety_bp
    from .sa8000.routes import sa8000_bp
    from .environment.routes import environment_bp
    from .esg.routes import esg_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(work_bp)
    app.register_blueprint(quality_bp)
    app.register_blueprint(maintenance_bp)
    app.register_blueprint(safety_bp)
    app.register_blueprint(sa8000_bp)
    app.register_blueprint(environment_bp)
    app.register_blueprint(esg_bp)

    with app.app_context():
        db.create_all()

    return app
