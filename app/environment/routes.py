from datetime import date, datetime

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..models_environment import (
    ConsumptionReading,
    EnvironmentalAspect,
    EnvironmentalCompliance,
    EnvironmentalDocument,
    EnvironmentalTarget,
    WasteRecord,
)

environment_bp = Blueprint("environment", __name__, url_prefix="/ambiente")


def owner_only():
    if not current_user.is_owner:
        abort(403)


def _parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _parse_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@environment_bp.route("/")
@login_required
def dashboard():
    owner_only()
    today = date.today()
    aspects = EnvironmentalAspect.query.order_by(EnvironmentalAspect.significance.desc()).all()
    upcoming_compliance = (
        EnvironmentalCompliance.query.filter(EnvironmentalCompliance.status != "completato")
        .order_by(EnvironmentalCompliance.deadline)
        .all()
    )
    targets = EnvironmentalTarget.query.order_by(EnvironmentalTarget.target_date).all()
    recent_waste = WasteRecord.query.order_by(WasteRecord.disposal_date.desc()).limit(5).all()
    total_waste_kg = db.session.query(db.func.coalesce(db.func.sum(WasteRecord.quantity_kg), 0)).scalar()
    return render_template(
        "environment/dashboard.html",
        aspects=aspects,
        upcoming_compliance=upcoming_compliance,
        targets=targets,
        recent_waste=recent_waste,
        total_waste_kg=total_waste_kg,
        today=today,
    )


@environment_bp.post("/aspetti")
@login_required
def create_aspect():
    owner_only()
    aspect = EnvironmentalAspect(
        activity=request.form.get("activity", "").strip(),
        aspect=request.form.get("aspect", "").strip(),
        impact_description=request.form.get("impact_description", "").strip() or None,
        significance=request.form.get("significance", "media"),
    )
    if not aspect.activity or not aspect.aspect:
        flash("Indica attività e aspetto ambientale.", "error")
        return redirect(url_for("environment.dashboard"))
    db.session.add(aspect)
    db.session.commit()
    flash("Aspetto ambientale registrato.", "success")
    return redirect(url_for("environment.dashboard"))


@environment_bp.route("/rifiuti")
@login_required
def waste():
    owner_only()
    records = WasteRecord.query.order_by(WasteRecord.disposal_date.desc()).all()
    total_kg = sum(r.quantity_kg for r in records)
    return render_template("environment/rifiuti.html", records=records, total_kg=total_kg)


@environment_bp.post("/rifiuti")
@login_required
def create_waste():
    owner_only()
    record = WasteRecord(
        cer_code=request.form.get("cer_code", "").strip(),
        waste_type=request.form.get("waste_type", "").strip(),
        quantity_kg=_parse_float(request.form.get("quantity_kg")),
        disposal_method=request.form.get("disposal_method", "").strip() or None,
        carrier_name=request.form.get("carrier_name", "").strip() or None,
        disposal_date=_parse_date(request.form.get("disposal_date")) or date.today(),
    )
    if not record.cer_code or not record.waste_type:
        flash("Indica codice CER e tipologia di rifiuto.", "error")
        return redirect(url_for("environment.waste"))
    db.session.add(record)
    db.session.commit()
    flash("Conferimento registrato.", "success")
    return redirect(url_for("environment.waste"))


@environment_bp.route("/consumi")
@login_required
def consumption():
    owner_only()
    readings = ConsumptionReading.query.order_by(ConsumptionReading.period_start.desc()).all()
    return render_template("environment/consumi.html", readings=readings)


@environment_bp.post("/consumi")
@login_required
def create_consumption():
    owner_only()
    reading = ConsumptionReading(
        resource_type=request.form.get("resource_type", "energia_elettrica"),
        period_start=_parse_date(request.form.get("period_start")),
        period_end=_parse_date(request.form.get("period_end")),
        quantity=_parse_float(request.form.get("quantity")),
        unit=request.form.get("unit", "kWh"),
        note=request.form.get("note", "").strip() or None,
    )
    if not reading.period_start or not reading.period_end:
        flash("Indica il periodo di riferimento della lettura.", "error")
        return redirect(url_for("environment.consumption"))
    db.session.add(reading)
    db.session.commit()
    flash("Consumo registrato.", "success")
    return redirect(url_for("environment.consumption"))


@environment_bp.route("/obiettivi")
@login_required
def targets():
    owner_only()
    items = EnvironmentalTarget.query.order_by(EnvironmentalTarget.target_date).all()
    return render_template("environment/obiettivi.html", targets=items)


@environment_bp.post("/obiettivi")
@login_required
def create_target():
    owner_only()
    target = EnvironmentalTarget(
        description=request.form.get("description", "").strip(),
        indicator=request.form.get("indicator", "").strip() or None,
        baseline_value=_parse_float(request.form.get("baseline_value"), None) if request.form.get("baseline_value") else None,
        target_value=_parse_float(request.form.get("target_value"), None) if request.form.get("target_value") else None,
        target_date=_parse_date(request.form.get("target_date")),
    )
    if not target.description:
        flash("Descrivi l'obiettivo ambientale.", "error")
        return redirect(url_for("environment.targets"))
    db.session.add(target)
    db.session.commit()
    flash("Obiettivo registrato.", "success")
    return redirect(url_for("environment.targets"))


@environment_bp.post("/obiettivi/<int:target_id>/stato")
@login_required
def update_target_status(target_id):
    owner_only()
    target = db.get_or_404(EnvironmentalTarget, target_id)
    target.status = request.form.get("status", target.status)
    db.session.commit()
    flash("Obiettivo aggiornato.", "success")
    return redirect(url_for("environment.targets"))


@environment_bp.route("/adempimenti")
@login_required
def compliance():
    owner_only()
    items = EnvironmentalCompliance.query.order_by(EnvironmentalCompliance.deadline).all()
    today = date.today()
    return render_template("environment/adempimenti.html", items=items, today=today)


@environment_bp.post("/adempimenti")
@login_required
def create_compliance():
    owner_only()
    item = EnvironmentalCompliance(
        requirement=request.form.get("requirement", "").strip(),
        deadline=_parse_date(request.form.get("deadline")),
    )
    if not item.requirement:
        flash("Indica l'adempimento normativo.", "error")
        return redirect(url_for("environment.compliance"))
    db.session.add(item)
    db.session.commit()
    flash("Adempimento registrato.", "success")
    return redirect(url_for("environment.compliance"))


@environment_bp.post("/adempimenti/<int:item_id>/completa")
@login_required
def complete_compliance(item_id):
    owner_only()
    item = db.get_or_404(EnvironmentalCompliance, item_id)
    item.status = "completato"
    item.completed_at = datetime.utcnow()
    db.session.commit()
    flash("Adempimento completato.", "success")
    return redirect(url_for("environment.compliance"))


@environment_bp.route("/documenti")
@login_required
def documents():
    owner_only()
    category = request.args.get("categoria", "")
    query = EnvironmentalDocument.query
    if category:
        query = query.filter_by(category=category)
    docs = query.order_by(EnvironmentalDocument.category, EnvironmentalDocument.code, EnvironmentalDocument.title).all()
    return render_template("environment/documenti.html", docs=docs, selected_category=category)


@environment_bp.route("/documenti/<int:doc_id>/scarica")
@login_required
def download_document(doc_id):
    owner_only()
    doc = db.get_or_404(EnvironmentalDocument, doc_id)
    return send_from_directory(current_app.static_folder, doc.file_path, as_attachment=True)
