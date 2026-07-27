"""Modelli per l'area ESG / Bilancio di sostenibilità.

Sostituisce il precedente modello semplificato (ESGIndicator/ESGMeasurement/
ESGTarget) con un impianto completo a "rapporto" annuale: ogni ESGReport
raccoglie sezioni testuali, KPI, temi materiali, piano di miglioramento,
coinvolgimento stakeholder, presidi di processo e approvazioni interne.
"""

from datetime import datetime
from .extensions import db


class ESGReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, unique=True)
    title = db.Column(db.String(255), nullable=False, default="Rapporto di sostenibilità")
    legal_name = db.Column(db.String(255), nullable=True)
    report_type = db.Column(db.String(100), nullable=False, default="Rapporto volontario ESG")
    version = db.Column(db.String(20), nullable=False, default="0.1")
    status = db.Column(db.String(30), nullable=False, default="bozza")  # bozza|raccolta_dati|in_revisione|restituito|approvato|pubblicato
    reporting_period_start = db.Column(db.Date, nullable=True)
    reporting_period_end = db.Column(db.Date, nullable=True)
    reporting_boundary = db.Column(db.Text, nullable=True)
    currency = db.Column(db.String(10), nullable=True)
    reporting_framework = db.Column(db.String(255), nullable=True)
    contact_email = db.Column(db.String(255), nullable=True)
    methodology_note = db.Column(db.Text, nullable=True)
    management_statement = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    sections = db.relationship(
        "ESGSectionContent", backref="report", lazy=True,
        order_by="ESGSectionContent.sort_order", cascade="all, delete-orphan",
    )
    metrics = db.relationship(
        "ESGMetric", backref="report", lazy=True,
        order_by="ESGMetric.sort_order", cascade="all, delete-orphan",
    )
    topics = db.relationship(
        "ESGTopic", backref="report", lazy=True,
        order_by="ESGTopic.sort_order", cascade="all, delete-orphan",
    )
    actions = db.relationship("ESGActionPlan", backref="report", lazy=True, cascade="all, delete-orphan")
    stakeholders = db.relationship("ESGStakeholderEngagement", backref="report", lazy=True, cascade="all, delete-orphan")
    processes = db.relationship("ESGProcessIntegration", backref="report", lazy=True, cascade="all, delete-orphan")
    approvals = db.relationship("ESGApproval", backref="report", lazy=True, cascade="all, delete-orphan")


class ESGSectionContent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey("esg_report.id"), nullable=False)
    section_code = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(255), nullable=True)
    body = db.Column(db.Text, nullable=True)
    is_placeholder = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)


class ESGMetric(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey("esg_report.id"), nullable=False)
    pillar = db.Column(db.String(1), nullable=False)  # E | S | G
    code = db.Column(db.String(50), nullable=True)
    name = db.Column(db.String(255), nullable=False)
    value = db.Column(db.Float, nullable=True)
    previous_value = db.Column(db.Float, nullable=True)
    baseline_value = db.Column(db.Float, nullable=True)
    target_value = db.Column(db.Float, nullable=True)
    unit = db.Column(db.String(50), nullable=True)
    denominator_value = db.Column(db.Float, nullable=True)
    denominator_unit = db.Column(db.String(50), nullable=True)
    formula = db.Column(db.String(255), nullable=True)
    data_quality = db.Column(db.String(20), nullable=False, default="ND")  # misurato | stimato | ND
    methodology = db.Column(db.Text, nullable=True)
    source_ref = db.Column(db.Text, nullable=True)
    data_owner = db.Column(db.String(150), nullable=True)
    note = db.Column(db.Text, nullable=True)
    visible_in_report = db.Column(db.Boolean, nullable=False, default=True)
    is_placeholder = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)


class ESGTopic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey("esg_report.id"), nullable=False)
    code = db.Column(db.String(50), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    pillar = db.Column(db.String(1), nullable=False)
    description = db.Column(db.Text, nullable=True)
    organization_score = db.Column(db.Float, nullable=True)
    stakeholder_score = db.Column(db.Float, nullable=True)
    priority_level = db.Column(db.String(50), nullable=True)
    owner = db.Column(db.String(150), nullable=True)
    is_placeholder = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)


class ESGActionPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey("esg_report.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    objective = db.Column(db.Text, nullable=True)
    kpi_code = db.Column(db.String(50), nullable=True)
    baseline = db.Column(db.String(150), nullable=True)
    target = db.Column(db.String(150), nullable=True)
    responsible = db.Column(db.String(150), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="pianificato")  # pianificato | in_corso | completato
    verification = db.Column(db.Text, nullable=True)
    is_placeholder = db.Column(db.Boolean, nullable=False, default=False)


class ESGStakeholderEngagement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey("esg_report.id"), nullable=False)
    category = db.Column(db.String(150), nullable=False)
    channel = db.Column(db.String(150), nullable=True)
    period = db.Column(db.String(100), nullable=True)
    expectations = db.Column(db.Text, nullable=True)
    response = db.Column(db.Text, nullable=True)
    is_placeholder = db.Column(db.Boolean, nullable=False, default=False)


class ESGProcessIntegration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey("esg_report.id"), nullable=False)
    process = db.Column(db.String(150), nullable=False)
    owner = db.Column(db.String(150), nullable=True)
    control = db.Column(db.Text, nullable=True)
    frequency = db.Column(db.String(100), nullable=True)
    evidence_ref = db.Column(db.String(255), nullable=True)
    outcome = db.Column(db.String(150), nullable=True)
    is_placeholder = db.Column(db.Boolean, nullable=False, default=False)


class ESGApproval(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey("esg_report.id"), nullable=False)
    role = db.Column(db.String(150), nullable=False)
    signer_name = db.Column(db.String(150), nullable=True)
    method = db.Column(db.String(150), nullable=True)
    decision = db.Column(db.String(50), nullable=True)
    statement_text = db.Column(db.Text, nullable=True)
    signed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
