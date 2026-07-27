"""Modello per le compilazioni "paperless" dei moduli della libreria documentale.

Una CompiledModule nasce da un SA8000Document o EnvironmentalDocument (categoria
modulistica/modulo): il contenuto originale viene convertito in HTML e presentato
in un editor dentro l'app, cosi' l'operatore lo compila senza aprire Word.
"""

from datetime import datetime
from .extensions import db


class CompiledModule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(20), nullable=False)  # sa8000 | ambiente
    source_document_id = db.Column(db.Integer, nullable=False)
    source_title = db.Column(db.String(255), nullable=False)  # snapshot codice + titolo
    content_html = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="bozza")  # bozza | completato
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
