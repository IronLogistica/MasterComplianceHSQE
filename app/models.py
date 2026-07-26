from datetime import date, datetime
from flask_login import UserMixin
from .extensions import db, login_manager


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    pin = db.Column(db.String(20), unique=True, nullable=False)  # sostituire con hash in produzione avanzata
    role = db.Column(db.String(20), nullable=False, default="operator")  # operator | owner
    active = db.Column(db.Boolean, nullable=False, default=True)

    @property
    def is_owner(self):
        return self.role == "owner"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    article_code = db.Column(db.String(80), nullable=False)
    article_name = db.Column(db.String(160), nullable=False)
    phase = db.Column(db.String(100), nullable=False)
    planned_qty = db.Column(db.Integer, nullable=False, default=0)
    produced_qty = db.Column(db.Integer, nullable=False, default=0)
    priority = db.Column(db.String(20), nullable=False, default="normale")
    status = db.Column(db.String(30), nullable=False, default="da_avviare")
    quality_plan_ref = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    sessions = db.relationship("WorkSession", backref="job", lazy=True)


class WorkSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False)
    operator_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)
    pieces = db.Column(db.Integer, nullable=False, default=0)
    first_piece_status = db.Column(db.String(30), nullable=False, default="in_attesa")
    operator = db.relationship("User", foreign_keys=[operator_id])
    checks = db.relationship("QualityCheck", backref="session", lazy=True)

    @property
    def active(self):
        return self.ended_at is None


class QualityPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    article_code = db.Column(db.String(80), nullable=False, unique=True)
    revision = db.Column(db.String(30), nullable=False)
    document_url = db.Column(db.String(500), nullable=True)
    first_piece_required = db.Column(db.Boolean, nullable=False, default=True)
    controls_text = db.Column(db.Text, nullable=True)


class QualityCheck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("work_session.id"), nullable=False)
    check_name = db.Column(db.String(160), nullable=False)
    outcome = db.Column(db.String(30), nullable=False)  # conforme | non_conforme
    note = db.Column(db.Text, nullable=True)
    performed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class Anomaly(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey("work_session.id"), nullable=True)
    description = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20), nullable=False, default="media")
    status = db.Column(db.String(30), nullable=False, default="aperta")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)
    job = db.relationship("Job", backref="anomalies")


# --- Manutenzione macchinari (ISO 9001 §7.1.3 Infrastruttura) ---


class Technician(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    plans = db.relationship("MaintenancePlan", backref="technician", lazy=True)
    events = db.relationship("MaintenanceEvent", backref="technician", lazy=True)


class ControlType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    requires_photo = db.Column(db.Boolean, nullable=False, default=False)
    plans = db.relationship("MaintenancePlan", backref="control_type", lazy=True)


class Machine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    default_technician_id = db.Column(db.Integer, db.ForeignKey("technician.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    default_technician = db.relationship("Technician", foreign_keys=[default_technician_id])
    plans = db.relationship("MaintenancePlan", backref="machine", lazy=True, order_by="MaintenancePlan.next_due")
    events = db.relationship("MaintenanceEvent", backref="machine", lazy=True, order_by="MaintenanceEvent.performed_at.desc()")


class MaintenancePlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, db.ForeignKey("machine.id"), nullable=False)
    control_type_id = db.Column(db.Integer, db.ForeignKey("control_type.id"), nullable=False)
    technician_id = db.Column(db.Integer, db.ForeignKey("technician.id"), nullable=True)

    # Gestione locazione: manutenzione interna o presso fornitore esterno
    location = db.Column(db.String(30), nullable=False, default="interna")  # interna | fornitore
    contractor_name = db.Column(db.String(150), nullable=True)

    frequency_days = db.Column(db.Integer, nullable=False, default=30)
    next_due = db.Column(db.Date, nullable=False)
    photo_instructions = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="da_programmare")  # da_programmare | in_esecuzione | concluso
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class MaintenanceEvent(db.Model):
    """Registro storico interventi effettuati su un macchinario (richiesto ai fini ISO 9001)."""

    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, db.ForeignKey("machine.id"), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey("maintenance_plan.id"), nullable=True)
    technician_id = db.Column(db.Integer, db.ForeignKey("technician.id"), nullable=True)
    control_type_name = db.Column(db.String(100), nullable=False)
    outcome = db.Column(db.String(30), nullable=False, default="eseguito")  # eseguito | non_conforme
    note = db.Column(db.Text, nullable=True)
    photo_path = db.Column(db.String(300), nullable=True)
    performed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    plan = db.relationship("MaintenancePlan", backref="events")


# --- Sicurezza sul lavoro: formazione, DPI, cantieri (D.Lgs 81/08) ---


class TrainingCourse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(100), nullable=True)  # es. Formazione generale, RSPP, Antincendio, Primo soccorso...
    validity_months = db.Column(db.Integer, nullable=True)  # None = non scade (es. formazione generale)
    required_for_site = db.Column(db.Boolean, nullable=False, default=False)
    records = db.relationship("TrainingRecord", backref="course", lazy=True)


class TrainingRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("training_course.id"), nullable=False)
    completed_on = db.Column(db.Date, nullable=False)
    expires_on = db.Column(db.Date, nullable=True)
    certificate_path = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    worker = db.relationship("User", foreign_keys=[worker_id])

    @property
    def expired(self):
        return self.expires_on is not None and self.expires_on < date.today()


class PPEItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(10), nullable=True)  # I | II | III (D.Lgs 81/08 art. 74)
    replacement_months = db.Column(db.Integer, nullable=True)  # None = nessuna scadenza di sostituzione
    required_for_site = db.Column(db.Boolean, nullable=False, default=False)
    issues = db.relationship("PPEIssue", backref="item", lazy=True)


class PPEIssue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    ppe_item_id = db.Column(db.Integer, db.ForeignKey("ppe_item.id"), nullable=False)
    issued_on = db.Column(db.Date, nullable=False)
    expires_on = db.Column(db.Date, nullable=True)
    signature_path = db.Column(db.String(300), nullable=True)
    returned = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    worker = db.relationship("User", foreign_keys=[worker_id])

    @property
    def expired(self):
        return self.expires_on is not None and self.expires_on < date.today()


class Site(db.Model):
    """Cantiere (es. lavori di segnaletica stradale presso terzi)."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(255), nullable=True)
    client_name = db.Column(db.String(150), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="attivo")  # attivo | concluso
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    plans = db.relationship("SafetyPlan", backref="site", lazy=True, order_by="SafetyPlan.created_at.desc()")
    assignments = db.relationship("SiteWorker", backref="site", lazy=True)


class SafetyPlan(db.Model):
    """Documento POS/piano di sicurezza per il cantiere (caricato o redatto esternamente)."""

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey("site.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    document_path = db.Column(db.String(300), nullable=True)
    valid_from = db.Column(db.Date, nullable=True)
    valid_to = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class SiteWorker(db.Model):
    """Assegnazione di un operaio a un cantiere."""

    id = db.Column(db.Integer, primary_key=True)
    site_id = db.Column(db.Integer, db.ForeignKey("site.id"), nullable=False)
    worker_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    assigned_on = db.Column(db.Date, nullable=False, default=date.today)
    worker = db.relationship("User", foreign_keys=[worker_id])
