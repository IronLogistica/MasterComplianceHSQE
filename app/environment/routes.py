import os
from datetime import date, datetime

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..library_tools import document_to_html
from ..models_library import CompiledModule, CompiledModuleField
from ..models_environment import (
    ConsumptionReading,
    EnvironmentalAspect,
    EnvironmentalCompliance,
    EnvironmentalDocument,
    EnvironmentalTarget,
    WasteRecord,
)

def _initialize_structured_fields(compiled):
    """Converte il documento in campi testuali senza consentire HTML arbitrario."""
    from html import unescape
    import re
    plain = unescape(re.sub(r"<[^>]+>", "\n", compiled.content_html or ""))
    lines = [re.sub(r"\s+", " ", x).strip() for x in plain.splitlines()]
    lines = [x for x in lines if len(x) > 2]
    if not lines:
        lines = ["Contenuto del modulo"]
    # I blocchi restano leggibili e modificabili; l'originale è preservato in content_html.
    for i, line in enumerate(lines[:120]):
        db.session.add(CompiledModuleField(compilation_id=compiled.id, label=f"Campo {i+1}", value=line, sort_order=i))


def _save_structured_fields(compiled):
    import html
    for field in compiled.fields:
        field.value = (request.form.get(f"field_{field.id}") or "").strip()
    compiled.content_html = "".join(f"<p>{html.escape(f.value or '')}</p>" for f in compiled.fields)


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


@environment_bp.route("/documenti/<int:doc_id>/visualizza")
@login_required
def view_document(doc_id):
    owner_only()
    doc = db.get_or_404(EnvironmentalDocument, doc_id)
    abs_path = os.path.join(current_app.static_folder, doc.file_path)
    html = document_to_html(abs_path)
    return render_template("environment/visualizza.html", doc=doc, html=html)


@environment_bp.post("/documenti/<int:doc_id>/compila")
@login_required
def start_compilation(doc_id):
    owner_only()
    doc = db.get_or_404(EnvironmentalDocument, doc_id)
    abs_path = os.path.join(current_app.static_folder, doc.file_path)
    html = document_to_html(abs_path)
    if html is None:
        flash("Questo documento non e' ancora convertito in formato compilabile.", "error")
        return redirect(url_for("environment.documents"))
    title = f"{doc.code} — {doc.title}" if doc.code else doc.title
    compiled = CompiledModule(domain="ambiente", source_document_id=doc.id, source_title=title, content_html=html)
    db.session.add(compiled)
    db.session.flush()
    _initialize_structured_fields(compiled)
    db.session.commit()
    return redirect(url_for("environment.edit_compilation", compilation_id=compiled.id))


@environment_bp.route("/compilazioni")
@login_required
def compilations():
    owner_only()
    items = CompiledModule.query.filter_by(domain="ambiente").order_by(CompiledModule.updated_at.desc()).all()
    return render_template("environment/compilazioni.html", items=items)


@environment_bp.route("/compilazioni/<int:compilation_id>")
@login_required
def edit_compilation(compilation_id):
    owner_only()
    compiled = db.get_or_404(CompiledModule, compilation_id)
    if compiled.domain != "ambiente":
        abort(404)
    if not compiled.fields:
        _initialize_structured_fields(compiled); db.session.commit()
    return render_template("environment/compila.html", compiled=compiled)


@environment_bp.post("/compilazioni/<int:compilation_id>")
@login_required
def save_compilation(compilation_id):
    owner_only()
    compiled = db.get_or_404(CompiledModule, compilation_id)
    if compiled.domain != "ambiente":
        abort(404)
    _save_structured_fields(compiled)
    db.session.commit()
    flash("Compilazione salvata.", "success")
    return redirect(url_for("environment.edit_compilation", compilation_id=compiled.id))


@environment_bp.post("/compilazioni/<int:compilation_id>/stato")
@login_required
def update_compilation_status(compilation_id):
    owner_only()
    compiled = db.get_or_404(CompiledModule, compilation_id)
    if compiled.domain != "ambiente":
        abort(404)
    compiled.status = "completato" if compiled.status != "completato" else "bozza"
    db.session.commit()
    return redirect(url_for("environment.compilations"))


@environment_bp.route("/compilazioni/<int:compilation_id>/stampa")
@login_required
def print_compilation(compilation_id):
    owner_only()
    compiled = db.get_or_404(CompiledModule, compilation_id)
    if compiled.domain != "ambiente":
        abort(404)
    return render_template("environment/stampa.html", compiled=compiled)

# --- Registri ISO 14001 operativi ---
@environment_bp.route("/registro")
@login_required
def register():
    owner_only();from ..models_environment import EnvironmentalCorrectiveAction,EnvironmentalEvidence
    kind=request.args.get("tipo","aspetti");q=(request.args.get("q") or "").strip();status=(request.args.get("stato") or "").strip()
    models={"aspetti":EnvironmentalAspect,"rifiuti":WasteRecord,"consumi":ConsumptionReading,"obiettivi":EnvironmentalTarget,"adempimenti":EnvironmentalCompliance,"azioni":EnvironmentalCorrectiveAction}
    kind=kind if kind in models else "aspetti"
    model=models[kind];query=model.query
    if q:
        cols={"aspetti":[EnvironmentalAspect.activity,EnvironmentalAspect.aspect],"rifiuti":[WasteRecord.cer_code,WasteRecord.waste_type],"consumi":[ConsumptionReading.resource_type,ConsumptionReading.note],"obiettivi":[EnvironmentalTarget.description,EnvironmentalTarget.indicator],"adempimenti":[EnvironmentalCompliance.requirement],"azioni":[EnvironmentalCorrectiveAction.description,EnvironmentalCorrectiveAction.responsible]}[kind]
        query=query.filter(db.or_(*[c.ilike(f"%{q}%") for c in cols]))
    if status and hasattr(model,"status"):query=query.filter(model.status==status)
    items=query.order_by(model.id.desc()).all();evidence=EnvironmentalEvidence.query.filter_by(entity_type=kind).order_by(EnvironmentalEvidence.uploaded_at.desc()).all();actions=EnvironmentalCorrectiveAction.query.order_by(EnvironmentalCorrectiveAction.id.desc()).all()
    return render_template("environment/registro.html",kind=kind,items=items,evidence=evidence,actions=actions,q=q,status=status)

@environment_bp.post("/registro/<kind>/<int:item_id>/modifica")
@login_required
def register_edit(kind,item_id):
    owner_only();from ..models_environment import EnvironmentalCorrectiveAction
    models={"aspetti":EnvironmentalAspect,"rifiuti":WasteRecord,"consumi":ConsumptionReading,"obiettivi":EnvironmentalTarget,"adempimenti":EnvironmentalCompliance,"azioni":EnvironmentalCorrectiveAction};model=models.get(kind);item=db.get_or_404(model,item_id) if model else abort(404)
    allowed={"aspetti":["activity","aspect","impact_description","significance"],"rifiuti":["cer_code","waste_type","disposal_method","carrier_name"],"consumi":["resource_type","unit","note"],"obiettivi":["description","indicator","status"],"adempimenti":["requirement","status"],"azioni":["description","responsible","status"]}[kind]
    for f in allowed:
        if f in request.form:setattr(item,f,request.form[f].strip() or None)
    db.session.commit();flash("Voce aggiornata.","success");return redirect(url_for("environment.register",tipo=kind))

@environment_bp.post("/registro/<kind>/<int:item_id>/elimina")
@login_required
def register_delete(kind,item_id):
    owner_only();from ..models_environment import EnvironmentalCorrectiveAction,EnvironmentalEvidence;from ..upload_tools import remove_upload
    models={"aspetti":EnvironmentalAspect,"rifiuti":WasteRecord,"consumi":ConsumptionReading,"obiettivi":EnvironmentalTarget,"adempimenti":EnvironmentalCompliance,"azioni":EnvironmentalCorrectiveAction};model=models.get(kind);item=db.get_or_404(model,item_id) if model else abort(404)
    for ev in EnvironmentalEvidence.query.filter_by(entity_type=kind,entity_id=item_id).all():remove_upload(ev.file_path);db.session.delete(ev)
    db.session.delete(item);db.session.commit();flash("Voce eliminata.","success");return redirect(url_for("environment.register",tipo=kind))

@environment_bp.post("/registro/<kind>/<int:item_id>/evidenze")
@login_required
def register_evidence(kind,item_id):
    owner_only();from ..models_environment import EnvironmentalEvidence;from ..upload_tools import save_upload
    try:
        title=(request.form.get("title") or "").strip()
        if not title:raise ValueError("Il titolo dell'evidenza è obbligatorio.")
        path=save_upload(request.files.get("file"),"ambiente");db.session.add(EnvironmentalEvidence(entity_type=kind,entity_id=item_id,title=title,note=(request.form.get("note") or "").strip() or None,file_path=path));db.session.commit();flash("Evidenza caricata.","success")
    except ValueError as e:db.session.rollback();flash(str(e),"error")
    return redirect(url_for("environment.register",tipo=kind))

@environment_bp.post("/registro/<kind>/<int:item_id>/azioni")
@login_required
def register_action(kind,item_id):
    owner_only();from ..models_environment import EnvironmentalCorrectiveAction;from ..upload_tools import save_upload
    desc=(request.form.get("description") or "").strip()
    if not desc:flash("Descrivi l'azione correttiva.","error");return redirect(url_for("environment.register",tipo=kind))
    path=None
    try:
        if request.files.get("file") and request.files["file"].filename:path=save_upload(request.files["file"],"ambiente")
        db.session.add(EnvironmentalCorrectiveAction(entity_type=kind,entity_id=item_id,description=desc,responsible=(request.form.get("responsible") or "").strip() or None,due_date=_parse_date(request.form.get("due_date")),evidence_path=path));db.session.commit();flash("Azione correttiva aggiunta.","success")
    except ValueError as e:db.session.rollback();flash(str(e),"error")
    return redirect(url_for("environment.register",tipo=kind))

@environment_bp.post("/evidenze/<int:evidence_id>/elimina")
@login_required
def delete_evidence(evidence_id):
    owner_only();from ..models_environment import EnvironmentalEvidence;from ..upload_tools import remove_upload
    ev=db.get_or_404(EnvironmentalEvidence,evidence_id);kind=ev.entity_type;remove_upload(ev.file_path);db.session.delete(ev);db.session.commit();return redirect(url_for("environment.register",tipo=kind))

@environment_bp.post("/documenti/carica")
@login_required
def upload_document():
    owner_only();from ..upload_tools import save_upload
    try:
        title=(request.form.get("title") or "").strip()
        if not title:raise ValueError("Il titolo è obbligatorio.")
        path=save_upload(request.files.get("file"),"ambiente");db.session.add(EnvironmentalDocument(category=request.form.get("category","allegato"),code=(request.form.get("code") or "").strip() or None,title=title,file_path=path));db.session.commit();flash("Documento caricato.","success")
    except ValueError as e:db.session.rollback();flash(str(e),"error")
    return redirect(url_for("environment.documents"))

@environment_bp.post("/documenti/<int:doc_id>/elimina")
@login_required
def delete_document(doc_id):
    owner_only();from ..upload_tools import remove_upload
    doc=db.get_or_404(EnvironmentalDocument,doc_id);remove_upload(doc.file_path);db.session.delete(doc);db.session.commit();return redirect(url_for("environment.documents"))

@environment_bp.post("/documenti/<int:doc_id>/modifica")
@login_required
def edit_document(doc_id):
    owner_only();doc=db.get_or_404(EnvironmentalDocument,doc_id);title=(request.form.get("title") or "").strip()
    if not title:flash("Il titolo è obbligatorio.","error")
    else:doc.title=title;doc.code=(request.form.get("code") or "").strip() or None;doc.category=request.form.get("category",doc.category);db.session.commit();flash("Documento aggiornato.","success")
    return redirect(url_for("environment.documents"))
