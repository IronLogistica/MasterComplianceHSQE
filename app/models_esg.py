"""Modelli per l'area ESG / Bilancio di sostenibilità.

Il modulo ESG aggrega anche dati generati dagli altri moduli (formazione,
non conformità, rifiuti, consumi) al momento della generazione del report;
qui restano solo gli indicatori "manuali" che non hanno una fonte automatica.
"""

from datetime import datetime
from .extensions import db


class ESGIndicator(db.Model):
    """Catalogo indicatori KPI Environmental / Social / Governance."""

    id = db.Column(db.Integer, primary_key=True)
    pillar = db.Column(db.String(1), nullable=False)  # E | S | G
    code = db.Column(db.String(30), nullable=False, unique=True)
    name = db.Column(db.String(150), nullable=False)
    unit = db.Column(db.String(30), nullable=True)
    description = db.Column(db.Text, nullable=True)
    measurements = db.relationship(
        "ESGMeasurement", backref="indicator", lazy=True, order_by="ESGMeasurement.period_year.desc()"
    )
    targets = db.relationship("ESGTarget", backref="indicator", lazy=True)


class ESGMeasurement(db.Model):
    """Valore rilevato per un indicatore in un dato anno."""

    id = db.Column(db.Integer, primary_key=True)
    indicator_id = db.Column(db.Integer, db.ForeignKey("esg_indicator.id"), nullable=False)
    period_year = db.Column(db.Integer, nullable=False)
    value = db.Column(db.Float, nullable=False, default=0)
    source_note = db.Column(db.String(255), nullable=True)
    evidence_path = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class ESGTarget(db.Model):
    """Obiettivo futuro per un indicatore ESG."""

    id = db.Column(db.Integer, primary_key=True)
    indicator_id = db.Column(db.Integer, db.ForeignKey("esg_indicator.id"), nullable=False)
    target_value = db.Column(db.Float, nullable=False)
    target_year = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(255), nullable=True)


class ESGReport(db.Model):
    """Bilancio ESG generato/esportato per uno specifico anno."""

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    generated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    file_path = db.Column(db.String(300), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="bozza")  # bozza | pubblicato
    notes = db.Column(db.Text, nullable=True)
