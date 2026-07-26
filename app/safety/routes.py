import os
import uuid
from datetime import date, datetime, timedelta

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import (
    PPEIssue,
    PPEItem,
    SafetyPlan,
    Site,
    SiteWorker,
    TrainingCourse,
    TrainingRecord,
    User,
)

safety_bp = Blueprint("safety", __name__, url_prefix="/safety")

ALLOWED_DOC_EXT = {".png", ".jpg", ".jpeg", ".pdf"}
MAX_DOC_SIZE = 15 * 1024 * 1024  # 15 MB
UPLOAD_SUBDIR = os.path.join("uploads", "sicurezza")


def owner_only():
    if not current_user.is_owner:
        abort(403)


def _upload_folder():
    path = os.path.join(current_app.static_folder, UPLOAD_SUBDIR)
    os.makedirs(path, exist_ok=True)
    return path


def _save_document(file_storage):
    """Salva un certificato/documento (PNG, JPG o PDF) e restituisce il percorso relativo, o None."""
    if not file_storage or not file_storage.filename:
        return None
    ext = os.path.splitext(secure_filename(file_storage.filename))[1].lower()
    if ext not in ALLOWED_DOC_EXT:
        flash(f"Formato .{ext.lstrip('.')} non supportato: usa PNG, JPG o PDF.", "error")
        return None
    payload = file_storage.read()
    if not payload or len(payload) > MAX_DOC_SIZE:
        flash("Il file è vuoto o supera il limite di 15 MB.", "error")
        return None
    filename = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(_upload_folder(), filename), "wb") as out:
        out.write(payload)
    return f"{UPLOAD_SUBDIR}/{filename}".replace("\\", "/")


def _add_months(base_date, months):
    month_index = base_date.month - 1 + months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(
        base_date.day,
        [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1],
    )
    return date(year, month, day)


def compliance_status(worker):
    """Verifica se un operaio ha tutta la formazione e i DPI obbligatori per andare in cantiere.

    Restituisce un dict con esito complessivo e il dettaglio di cosa manca o è scaduto.
    """
    today = date.today()
    missing_courses, expired_courses = [], []
    for course in TrainingCourse.query.filter_by(required_for_site=True).all():
        record = (
            TrainingRecord.query.filter_by(worker_id=worker.id, course_id=course.id)
            .order_by(TrainingRecord.completed_on.desc())
            .first()
        )
        if not record:
            missing_courses.append(course.name)
        elif record.expires_on and record.expires_on < today:
            expired_courses.append(course.name)

    missing_ppe, expired_ppe = [], []
    for item in PPEItem.query.filter_by(required_for_site=True).all():
        issue = (
            PPEIssue.query.filter_by(worker_id=worker.id, ppe_item_id=item.id, returned=False)
            .order_by(PPEIssue.issued_on.desc())
            .first()
        )
        if not issue:
            missing_ppe.append(item.name)
        elif issue.expires_on and issue.expires_on < today:
            expired_ppe.append(item.name)

    problems = missing_courses + expired_courses + missing_ppe + expired_ppe
    return {
        "ok": not problems,
        "missing_courses": missing_courses,
        "expired_courses": expired_courses,
        "missing_ppe": missing_ppe,
        "expired_ppe": expired_ppe,
    }


@safety_bp.route("/")
@login_required
def dashboard():
    owner_only()
    horizon = date.today() + timedelta(days=30)
    expiring_trainings = (
        TrainingRecord.query.filter(TrainingRecord.expires_on.isnot(None), TrainingRecord.expires_on <= horizon)
        .order_by(TrainingRecord.expires_on)
        .all()
    )
    expiring_ppe = (
        PPEIssue.query.filter(PPEIssue.returned.is_(False), PPEIssue.expires_on.isnot(None), PPEIssue.expires_on <= horizon)
        .order_by(PPEIssue.expires_on)
        .all()
    )
    workers = User.query.filter_by(role="operator", active=True).order_by(User.name).all()
    return render_template(
        "safety/dashboard.html",
        expiring_trainings=expiring_trainings,
        expiring_ppe=expiring_ppe,
        workers=workers,
        today=date.today(),
    )


@safety_bp.route("/workers/<int:worker_id>")
@login_required
def worker_detail(worker_id):
    owner_only()
    worker = db.get_or_404(User, worker_id)
    trainings = TrainingRecord.query.filter_by(worker_id=worker.id).order_by(TrainingRecord.completed_on.desc()).all()
    ppe = PPEIssue.query.filter_by(worker_id=worker.id).order_by(PPEIssue.issued_on.desc()).all()
    courses = TrainingCourse.query.order_by(TrainingCourse.name).all()
    ppe_items = PPEItem.query.order_by(PPEItem.name).all()
    return render_template(
        "safety/worker_detail.html",
        worker=worker,
        trainings=trainings,
        ppe=ppe,
        courses=courses,
        ppe_items=ppe_items,
        status=compliance_status(worker),
        today=date.today(),
    )


@safety_bp.post("/workers/<int:worker_id>/trainings")
@login_required
def add_training(worker_id):
    owner_only()
    worker = db.get_or_404(User, worker_id)
    course_id = request.form.get("course_id")
    completed_raw = request.form.get("completed_on", "")
    if not course_id or not completed_raw:
        flash("Corso e data di svolgimento sono obbligatori.", "error")
        return redirect(url_for("safety.worker_detail", worker_id=worker.id))

    course = db.get_or_404(TrainingCourse, int(course_id))
    completed_on = datetime.strptime(completed_raw, "%Y-%m-%d").date()
    expires_on = _add_months(completed_on, course.validity_months) if course.validity_months else None
    certificate_path = _save_document(request.files.get("certificate"))

    db.session.add(
        TrainingRecord(
            worker_id=worker.id,
            course_id=course.id,
            completed_on=completed_on,
            expires_on=expires_on,
            certificate_path=certificate_path,
        )
    )
    db.session.commit()
    flash(f"Formazione registrata: {course.name}" + (f" (scade {expires_on.strftime('%d/%m/%Y')})" if expires_on else " (senza scadenza)."), "success")
    return redirect(url_for("safety.worker_detail", worker_id=worker.id))


@safety_bp.post("/workers/<int:worker_id>/ppe")
@login_required
def add_ppe(worker_id):
    owner_only()
    worker = db.get_or_404(User, worker_id)
    item_id = request.form.get("ppe_item_id")
    issued_raw = request.form.get("issued_on", "")
    if not item_id or not issued_raw:
        flash("DPI e data di consegna sono obbligatori.", "error")
        return redirect(url_for("safety.worker_detail", worker_id=worker.id))

    item = db.get_or_404(PPEItem, int(item_id))
    issued_on = datetime.strptime(issued_raw, "%Y-%m-%d").date()
    expires_on = _add_months(issued_on, item.replacement_months) if item.replacement_months else None
    signature_path = _save_document(request.files.get("signature"))

    db.session.add(
        PPEIssue(
            worker_id=worker.id,
            ppe_item_id=item.id,
            issued_on=issued_on,
            expires_on=expires_on,
            signature_path=signature_path,
        )
    )
    db.session.commit()
    flash(f"DPI consegnato: {item.name}", "success")
    return redirect(url_for("safety.worker_detail", worker_id=worker.id))


@safety_bp.post("/workers/<int:worker_id>/ppe/<int:issue_id>/return")
@login_required
def return_ppe(worker_id, issue_id):
    owner_only()
    issue = db.get_or_404(PPEIssue, issue_id)
    if issue.worker_id != worker_id:
        abort(404)
    issue.returned = True
    db.session.commit()
    flash("DPI segnato come restituito/sostituito.", "success")
    return redirect(url_for("safety.worker_detail", worker_id=worker_id))


@safety_bp.route("/courses", methods=["GET", "POST"])
@login_required
def courses():
    owner_only()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Il nome del corso è obbligatorio.", "error")
            return redirect(url_for("safety.courses"))
        validity = request.form.get("validity_months") or None
        db.session.add(
            TrainingCourse(
                name=name,
                category=request.form.get("category", "").strip() or None,
                validity_months=int(validity) if validity else None,
                required_for_site="required_for_site" in request.form,
            )
        )
        db.session.commit()
        flash("Corso aggiunto al catalogo.", "success")
        return redirect(url_for("safety.courses"))
    return render_template("safety/courses.html", courses=TrainingCourse.query.order_by(TrainingCourse.name).all())


@safety_bp.route("/ppe-catalog", methods=["GET", "POST"])
@login_required
def ppe_catalog():
    owner_only()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Il nome del DPI è obbligatorio.", "error")
            return redirect(url_for("safety.ppe_catalog"))
        replacement = request.form.get("replacement_months") or None
        db.session.add(
            PPEItem(
                name=name,
                category=request.form.get("category", "").strip() or None,
                replacement_months=int(replacement) if replacement else None,
                required_for_site="required_for_site" in request.form,
            )
        )
        db.session.commit()
        flash("DPI aggiunto al catalogo.", "success")
        return redirect(url_for("safety.ppe_catalog"))
    return render_template("safety/ppe_catalog.html", items=PPEItem.query.order_by(PPEItem.name).all())


@safety_bp.route("/sites")
@login_required
def sites():
    owner_only()
    return render_template("safety/sites.html", sites=Site.query.order_by(Site.start_date.desc()).all())


@safety_bp.post("/sites")
@login_required
def create_site():
    owner_only()
    name = request.form.get("name", "").strip()
    if not name:
        flash("Il nome del cantiere è obbligatorio.", "error")
        return redirect(url_for("safety.sites"))
    start_raw = request.form.get("start_date", "")
    end_raw = request.form.get("end_date", "")
    db.session.add(
        Site(
            name=name,
            address=request.form.get("address", "").strip() or None,
            client_name=request.form.get("client_name", "").strip() or None,
            start_date=datetime.strptime(start_raw, "%Y-%m-%d").date() if start_raw else None,
            end_date=datetime.strptime(end_raw, "%Y-%m-%d").date() if end_raw else None,
        )
    )
    db.session.commit()
    flash("Cantiere creato.", "success")
    return redirect(url_for("safety.sites"))


@safety_bp.route("/sites/<int:site_id>")
@login_required
def site_detail(site_id):
    owner_only()
    site = db.get_or_404(Site, site_id)
    assigned_ids = {a.worker_id for a in site.assignments}
    available_workers = User.query.filter(User.role == "operator", User.active.is_(True), ~User.id.in_(assigned_ids or [0])).order_by(User.name).all()
    compliance = {a.worker_id: compliance_status(a.worker) for a in site.assignments}
    return render_template(
        "safety/site_detail.html",
        site=site,
        available_workers=available_workers,
        compliance=compliance,
    )


@safety_bp.post("/sites/<int:site_id>/assign")
@login_required
def assign_worker(site_id):
    owner_only()
    site = db.get_or_404(Site, site_id)
    worker_id = request.form.get("worker_id")
    if not worker_id:
        flash("Seleziona un operaio da assegnare.", "error")
        return redirect(url_for("safety.site_detail", site_id=site.id))
    if SiteWorker.query.filter_by(site_id=site.id, worker_id=int(worker_id)).first():
        flash("Operaio già assegnato a questo cantiere.", "error")
        return redirect(url_for("safety.site_detail", site_id=site.id))
    db.session.add(SiteWorker(site_id=site.id, worker_id=int(worker_id)))
    db.session.commit()
    flash("Operaio assegnato al cantiere.", "success")
    return redirect(url_for("safety.site_detail", site_id=site.id))


@safety_bp.post("/sites/<int:site_id>/unassign/<int:worker_id>")
@login_required
def unassign_worker(site_id, worker_id):
    owner_only()
    assignment = SiteWorker.query.filter_by(site_id=site_id, worker_id=worker_id).first()
    if assignment:
        db.session.delete(assignment)
        db.session.commit()
        flash("Operaio rimosso dal cantiere.", "success")
    return redirect(url_for("safety.site_detail", site_id=site_id))


@safety_bp.post("/sites/<int:site_id>/plans")
@login_required
def upload_plan(site_id):
    owner_only()
    site = db.get_or_404(Site, site_id)
    title = request.form.get("title", "").strip() or "Piano di sicurezza"
    document_path = _save_document(request.files.get("document"))
    valid_from = request.form.get("valid_from", "")
    valid_to = request.form.get("valid_to", "")
    db.session.add(
        SafetyPlan(
            site_id=site.id,
            title=title,
            document_path=document_path,
            valid_from=datetime.strptime(valid_from, "%Y-%m-%d").date() if valid_from else None,
            valid_to=datetime.strptime(valid_to, "%Y-%m-%d").date() if valid_to else None,
        )
    )
    db.session.commit()
    flash("Documento di sicurezza caricato.", "success")
    return redirect(url_for("safety.site_detail", site_id=site.id))
