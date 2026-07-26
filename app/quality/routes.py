from flask import Blueprint, flash, redirect, request, url_for
from flask_login import current_user, login_required
from ..extensions import db
from ..models import QualityCheck, WorkSession

quality_bp = Blueprint("quality", __name__, url_prefix="/quality")


@quality_bp.post("/sessions/<int:session_id>/first-piece")
@login_required
def first_piece(session_id):
    session = db.get_or_404(WorkSession, session_id)
    if session.operator_id != current_user.id or not session.active:
        return ("Operazione non consentita", 403)
    outcome = request.form.get("outcome", "non_conforme")
    session.first_piece_status = outcome
    db.session.add(QualityCheck(session_id=session.id, check_name="Controllo primo pezzo", outcome=outcome, note=request.form.get("note", "")))
    db.session.commit()
    flash("Controllo primo pezzo registrato.", "success" if outcome == "conforme" else "error")
    return redirect(url_for("work.my_work"))


@quality_bp.post("/sessions/<int:session_id>/check")
@login_required
def check(session_id):
    session = db.get_or_404(WorkSession, session_id)
    if session.operator_id != current_user.id or not session.active:
        return ("Operazione non consentita", 403)
    db.session.add(QualityCheck(session_id=session.id, check_name=request.form.get("name", "Controllo produzione"), outcome=request.form.get("outcome", "conforme"), note=request.form.get("note", "")))
    db.session.commit()
    flash("Controllo qualità registrato.", "success")
    return redirect(url_for("work.my_work"))
