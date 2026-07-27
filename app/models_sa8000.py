"""Modelli per l'area SA8000 (diritti dei lavoratori, segnalazioni, audit).

La formazione sui diritti dei lavoratori (SA8000) non ha un modello dedicato:
riusa TrainingCourse/TrainingRecord del modulo sicurezza, taggando il corso
con category="SA8000", per evitare di duplicare la stessa tabella.
"""

from datetime import date, datetime
from .extensions import db

REPORT_CATEGORIES = (
    "lavoro_minorile",
    "lavoro_forzato",
    "salute_sicurezza",
    "liberta_associazione",
    "discriminazione",
    "orario_retribuzione",
    "disciplina",
    "altro",
)


class SA8000Report(db.Model):
    """Segnalazione dei lavoratori (meccanismo di grievance previsto da SA8000)."""

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(40), nullable=False, default="altro")
    description = db.Column(db.Text, nullable=False)
    anonymous = db.Column(db.Boolean, nullable=False, default=True)
    reporter_name = db.Column(db.String(150), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="aperta")  # aperta | in_istruttoria | chiusa
    resolution_text = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)


class SA8000NonConformity(db.Model):
    """Non conformità rilevata rispetto ai requisiti SA8000."""

    id = db.Column(db.Integer, primary_key=True)
    clause = db.Column(db.String(120), nullable=False)  # es. "Orario di lavoro", "Libertà di associazione"
    description = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20), nullable=False, default="media")  # bassa | media | alta
    status = db.Column(db.String(30), nullable=False, default="aperta")  # aperta | in_corso | chiusa
    root_cause = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)
    actions = db.relationship(
        "SA8000CorrectiveAction",
        backref="non_conformity",
        lazy=True,
        order_by="SA8000CorrectiveAction.due_date",
    )


class SA8000CorrectiveAction(db.Model):
    """Azione correttiva collegata a una non conformità SA8000."""

    id = db.Column(db.Integer, primary_key=True)
    non_conformity_id = db.Column(db.Integer, db.ForeignKey("sa8000_non_conformity.id"), nullable=False)
    description = db.Column(db.Text, nullable=False)
    responsible = db.Column(db.String(150), nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="da_fare")  # da_fare | in_corso | completata | verificata_efficace
    completed_at = db.Column(db.DateTime, nullable=True)
    evidence_path = db.Column(db.String(300), nullable=True)


class SA8000Audit(db.Model):
    """Audit interno, esterno o di ente di certificazione terza parte."""

    id = db.Column(db.Integer, primary_key=True)
    audit_date = db.Column(db.Date, nullable=False, default=date.today)
    audit_type = db.Column(db.String(30), nullable=False, default="interno")  # interno | esterno | ente_terza_parte
    auditor_name = db.Column(db.String(150), nullable=True)
    scope = db.Column(db.String(255), nullable=True)
    outcome_summary = db.Column(db.Text, nullable=True)
    document_path = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class SA8000Document(db.Model):
    """Documento della libreria SA8000 (manuale, procedure, modulistica, allegati)."""

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(20), nullable=False)  # manuale | procedura | modulistica | allegato
    code = db.Column(db.String(30), nullable=True)  # es. PROC-980, MOD-940-01
    title = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(400), nullable=False, unique=True)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class SA8000Evidence(db.Model):
    """Evidenza allegata a registri SA8000."""
    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(30), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    note = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(400), nullable=False)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
