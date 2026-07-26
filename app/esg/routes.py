import os
import uuid
from datetime import date, datetime

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from openpyxl import Workbook

from ..extensions import db
from ..models import Anomaly, PPEIssue, TrainingRecord
from ..models_environment import ConsumptionReading, WasteRecord
from ..models_esg import ESGIndicator, ESGMeasurement, ESGReport, ESGTarget
from ..models_sa8000 import SA8000CorrectiveAction, SA8000NonConformity, SA8000Report

esg_bp = Blueprint("esg", __name__, url_prefix="/esg")

UPLOAD_SUBDIR = os.path.join("uploads", "esg")


def owner_only():
    if not current_user.is_owner:
        abort(403)


def _upload_folder():
    path = os.path.join(current_app.static_folder, UPLOAD_SUBDIR)
    os.makedirs(path, exist_ok=True)
    return path


def _auto_kpis_for_year(year):
    """KPI ricavati automaticamente dagli altri moduli, per un dato anno."""
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    training_hours_proxy = TrainingRecord.query.filter(
        TrainingRecord.completed_on >= start, TrainingRecord.completed_on <= end
    ).count()
    ppe_issued = PPEIssue.query.filter(PPEIssue.issued_on >= start, PPEIssue.issued_on <= end).count()
    quality_anomalies_open = Anomaly.query.filter(Anomaly.status != "chiusa").count()
    sa8000_reports_open = SA8000Report.query.filter(SA8000Report.status != "chiusa").count()
    sa8000_ncs_open = SA8000NonConformity.query.filter(SA8000NonConformity.status != "chiusa").count()
    sa8000_actions_pending = SA8000CorrectiveAction.query.filter(
        SA8000CorrectiveAction.status.notin_(["completata", "verificata_efficace"])
    ).count()
    waste_kg = (
        db.session.query(db.func.coalesce(db.func.sum(WasteRecord.quantity_kg), 0))
        .filter(WasteRecord.disposal_date >= start, WasteRecord.disposal_date <= end)
        .scalar()
    )
    consumption_by_resource = (
        db.session.query(ConsumptionReading.resource_type, db.func.coalesce(db.func.sum(ConsumptionReading.quantity), 0))
        .filter(ConsumptionReading.period_start >= start, ConsumptionReading.period_start <= end)
        .group_by(ConsumptionReading.resource_type)
        .all()
    )
    return {
        "S · Corsi formazione completati nell'anno": training_hours_proxy,
        "S · DPI consegnati nell'anno": ppe_issued,
        "G · Non conformità qualità aperte (attuale)": quality_anomalies_open,
        "S · Segnalazioni SA8000 aperte (attuale)": sa8000_reports_open,
        "S · Non conformità SA8000 aperte (attuale)": sa8000_ncs_open,
        "S · Azioni correttive SA8000 in sospeso (attuale)": sa8000_actions_pending,
        "E · Rifiuti prodotti nell'anno (kg)": round(waste_kg or 0, 1),
        **{f"E · Consumo {res} nell'anno": round(qty, 1) for res, qty in consumption_by_resource},
    }


@esg_bp.route("/")
@login_required
def dashboard():
    owner_only()
    indicators = ESGIndicator.query.order_by(ESGIndicator.pillar, ESGIndicator.code).all()
    current_year = date.today().year
    auto_kpis = _auto_kpis_for_year(current_year)
    reports = ESGReport.query.order_by(ESGReport.year.desc()).all()
    return render_template(
        "esg/dashboard.html",
        indicators=indicators,
        auto_kpis=auto_kpis,
        current_year=current_year,
        reports=reports,
    )


@esg_bp.route("/indicatori")
@login_required
def indicators():
    owner_only()
    items = ESGIndicator.query.order_by(ESGIndicator.pillar, ESGIndicator.code).all()
    return render_template("esg/indicatori.html", indicators=items)


@esg_bp.post("/indicatori")
@login_required
def create_indicator():
    owner_only()
    indicator = ESGIndicator(
        pillar=request.form.get("pillar", "E"),
        code=request.form.get("code", "").strip(),
        name=request.form.get("name", "").strip(),
        unit=request.form.get("unit", "").strip() or None,
        description=request.form.get("description", "").strip() or None,
    )
    if not indicator.code or not indicator.name:
        flash("Indica codice e nome dell'indicatore.", "error")
        return redirect(url_for("esg.indicators"))
    db.session.add(indicator)
    db.session.commit()
    flash("Indicatore ESG creato.", "success")
    return redirect(url_for("esg.indicators"))


@esg_bp.post("/indicatori/<int:indicator_id>/misurazioni")
@login_required
def create_measurement(indicator_id):
    owner_only()
    indicator = db.get_or_404(ESGIndicator, indicator_id)
    try:
        value = float(request.form.get("value", 0))
        period_year = int(request.form.get("period_year", date.today().year))
    except ValueError:
        flash("Valore o anno non validi.", "error")
        return redirect(url_for("esg.indicators"))
    measurement = ESGMeasurement(
        indicator_id=indicator.id,
        period_year=period_year,
        value=value,
        source_note=request.form.get("source_note", "").strip() or None,
    )
    db.session.add(measurement)
    db.session.commit()
    flash("Misurazione registrata.", "success")
    return redirect(url_for("esg.indicators"))


@esg_bp.post("/indicatori/<int:indicator_id>/obiettivi")
@login_required
def create_target(indicator_id):
    owner_only()
    indicator = db.get_or_404(ESGIndicator, indicator_id)
    try:
        target_value = float(request.form.get("target_value", 0))
        target_year = int(request.form.get("target_year", date.today().year + 1))
    except ValueError:
        flash("Valore obiettivo o anno non validi.", "error")
        return redirect(url_for("esg.indicators"))
    target = ESGTarget(
        indicator_id=indicator.id,
        target_value=target_value,
        target_year=target_year,
        note=request.form.get("note", "").strip() or None,
    )
    db.session.add(target)
    db.session.commit()
    flash("Obiettivo ESG registrato.", "success")
    return redirect(url_for("esg.indicators"))


@esg_bp.post("/report/genera")
@login_required
def generate_report():
    owner_only()
    try:
        year = int(request.form.get("year", date.today().year))
    except ValueError:
        flash("Anno non valido.", "error")
        return redirect(url_for("esg.dashboard"))

    wb = Workbook()
    ws_kpi = wb.active
    ws_kpi.title = "KPI automatici"
    ws_kpi.append(["Indicatore", "Valore", "Anno"])
    for name, value in _auto_kpis_for_year(year).items():
        ws_kpi.append([name, value, year])

    ws_ind = wb.create_sheet("Indicatori manuali")
    ws_ind.append(["Pilastro", "Codice", "Nome", "Unità", "Valore anno", "Obiettivo", "Anno obiettivo"])
    for indicator in ESGIndicator.query.order_by(ESGIndicator.pillar, ESGIndicator.code).all():
        measurement = next((m for m in indicator.measurements if m.period_year == year), None)
        target = next((t for t in indicator.targets if t.target_year >= year), None)
        ws_ind.append([
            indicator.pillar,
            indicator.code,
            indicator.name,
            indicator.unit or "",
            measurement.value if measurement else "",
            target.target_value if target else "",
            target.target_year if target else "",
        ])

    filename = f"bilancio-esg-{year}-{uuid.uuid4().hex[:8]}.xlsx"
    wb.save(os.path.join(_upload_folder(), filename))
    file_path = f"{UPLOAD_SUBDIR}/{filename}".replace("\\", "/")

    report = ESGReport(year=year, file_path=file_path, generated_at=datetime.utcnow())
    db.session.add(report)
    db.session.commit()
    flash(f"Bilancio ESG {year} generato.", "success")
    return redirect(url_for("esg.dashboard"))


@esg_bp.route("/report/<int:report_id>/scarica")
@login_required
def download_report(report_id):
    owner_only()
    report = db.get_or_404(ESGReport, report_id)
    if not report.file_path:
        abort(404)
    directory = current_app.static_folder
    return send_from_directory(directory, report.file_path, as_attachment=True)
