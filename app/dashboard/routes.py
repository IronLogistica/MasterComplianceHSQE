from datetime import date
from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required
from sqlalchemy import func
from ..extensions import db
from ..models import Anomaly, Job, WorkSession

dashboard_bp = Blueprint("dashboard", __name__)


def owner_only():
    if not current_user.is_owner:
        abort(403)


@dashboard_bp.route("/")
@login_required
def board():
    owner_only()
    jobs = Job.query.order_by(Job.priority.desc(), Job.created_at.desc()).all()
    active = WorkSession.query.filter_by(ended_at=None).all()
    anomalies = Anomaly.query.filter(Anomaly.status != "chiusa").order_by(Anomaly.created_at.desc()).all()
    today_pieces = db.session.query(func.coalesce(func.sum(WorkSession.pieces), 0)).filter(func.date(WorkSession.started_at) == date.today()).scalar()
    return render_template("dashboard/board.html", jobs=jobs, active=active, anomalies=anomalies, today_pieces=today_pieces)


@dashboard_bp.post("/anomalies/<int:anomaly_id>/close")
@login_required
def close_anomaly(anomaly_id):
    owner_only()
    anomaly = db.get_or_404(Anomaly, anomaly_id)
    anomaly.status = "chiusa"
    db.session.commit()
    return ("", 204)
