"""Modelli per l'area ambientale (famiglia ISO 14000)."""

from datetime import date, datetime
from .extensions import db


class EnvironmentalAspect(db.Model):
    """Aspetti e impatti ambientali di un'attività (ISO 14001 §6.1.2)."""

    id = db.Column(db.Integer, primary_key=True)
    activity = db.Column(db.String(150), nullable=False)
    aspect = db.Column(db.String(150), nullable=False)  # es. emissioni, scarichi idrici, rifiuti, consumo energia
    impact_description = db.Column(db.Text, nullable=True)
    significance = db.Column(db.String(20), nullable=False, default="media")  # bassa | media | alta
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class WasteRecord(db.Model):
    """Registro rifiuti (formulario di identificazione rifiuti - FIR)."""

    id = db.Column(db.Integer, primary_key=True)
    cer_code = db.Column(db.String(20), nullable=False)
    waste_type = db.Column(db.String(150), nullable=False)
    quantity_kg = db.Column(db.Float, nullable=False, default=0)
    disposal_method = db.Column(db.String(100), nullable=True)  # recupero | smaltimento
    carrier_name = db.Column(db.String(150), nullable=True)
    disposal_date = db.Column(db.Date, nullable=False, default=date.today)
    document_path = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class ConsumptionReading(db.Model):
    """Lettura periodica di un consumo (energia, acqua, gas, carburante)."""

    id = db.Column(db.Integer, primary_key=True)
    resource_type = db.Column(db.String(40), nullable=False)  # energia_elettrica | acqua | gas_metano | carburante
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=0)
    unit = db.Column(db.String(20), nullable=False, default="kWh")
    note = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class EnvironmentalTarget(db.Model):
    """Obiettivo ambientale (ISO 14001 §6.2)."""

    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    indicator = db.Column(db.String(150), nullable=True)
    baseline_value = db.Column(db.Float, nullable=True)
    target_value = db.Column(db.Float, nullable=True)
    target_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="in_corso")  # in_corso | raggiunto | non_raggiunto
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class EnvironmentalCompliance(db.Model):
    """Adempimento normativo ambientale (AUA, MUD, registro carico/scarico, ecc.)."""

    id = db.Column(db.Integer, primary_key=True)
    requirement = db.Column(db.String(150), nullable=False)
    deadline = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="da_fare")  # da_fare | in_corso | completato
    document_path = db.Column(db.String(300), nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
