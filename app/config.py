import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "sviluppo-sostituire-prima-della-pubblicazione")
    database_url = os.getenv("DATABASE_URL", "sqlite:///masterwork_quality.db")
    # Railway fornisce spesso postgres://; SQLAlchemy richiede postgresql://
    SQLALCHEMY_DATABASE_URI = database_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

# Limite applicativo per gli allegati (validato anche da upload_tools).
Config.MAX_CONTENT_LENGTH = 16 * 1024 * 1024
