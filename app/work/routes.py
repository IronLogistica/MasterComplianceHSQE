from datetime import datetime
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from ..extensions import db
from ..models import Anomaly, Job, WorkSession

work_bp = Blueprint("work", __name__, url_prefix="/work")


@work_bp.route("/")
@login_required
def my_work():
    session = WorkSession.query.filter_by(operator_id=current_user.id, ended_at=None).first()
    jobs = Job.query.filter(Job.status.in_(["da_avviare", "in_corso", "bloccato"])).order_by(Job.priority.desc()).all()
    return render_template("work/my_work.html", session=session, jobs=jobs)


@work_bp.post("/jobs/<int:job_id>/start")
@login_required
def start(job_id):
    existing = WorkSession.query.filter_by(operator_id=current_user.id, ended_at=None).first()
    if existing:
        flash("Hai già un lavoro attivo: chiudilo prima di avviarne un altro.", "error")
        return redirect(url_for("work.my_work"))
    job = db.get_or_404(Job, job_id)
    db.session.add(WorkSession(job_id=job.id, operator_id=current_user.id))
    job.status = "in_corso"
    db.session.commit()
    flash("Lavoro avviato. Esegui il controllo primo pezzo.", "success")
    return redirect(url_for("work.my_work"))


@work_bp.post("/sessions/<int:session_id>/pieces")
@login_required
def update_pieces(session_id):
    session = db.get_or_404(WorkSession, session_id)
    if session.operator_id != current_user.id or not session.active:
        return ("Operazione non consentita", 403)
    pieces = max(0, int(request.form.get("pieces", 0)))
    session.pieces = pieces
    session.job.produced_qty = sum(item.pieces for item in session.job.sessions)
    db.session.commit()
    return redirect(url_for("work.my_work"))


@work_bp.post("/sessions/<int:session_id>/end")
@login_required
def end(session_id):
    session = db.get_or_404(WorkSession, session_id)
    if session.operator_id != current_user.id or not session.active:
        return ("Operazione non consentita", 403)
    if session.first_piece_status != "conforme":
        flash("Non puoi chiudere senza un primo pezzo conforme.", "error")
        return redirect(url_for("work.my_work"))
    session.ended_at = datetime.utcnow()
    session.job.status = "completato" if session.job.produced_qty >= session.job.planned_qty else "da_avviare"
    db.session.commit()
    flash("Lavoro chiuso correttamente.", "success")
    return redirect(url_for("work.my_work"))


@work_bp.post("/sessions/<int:session_id>/anomalies")
@login_required
def anomaly(session_id):
    session = db.get_or_404(WorkSession, session_id)
    if session.operator_id != current_user.id:
        return ("Operazione non consentita", 403)
    description = request.form.get("description", "").strip()
    if description:
        db.session.add(Anomaly(job_id=session.job_id, session_id=session.id, description=description, severity=request.form.get("severity", "media")))
        session.job.status = "bloccato"
        db.session.commit()
        flash("Anomalia inviata alla titolare.", "success")
    return redirect(url_for("work.my_work"))
