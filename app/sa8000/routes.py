import os
from datetime import date, datetime

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..library_tools import document_to_html
from ..models_library import CompiledModule, CompiledModuleField
from ..models_sa8000 import (
    REPORT_CATEGORIES,
    SA8000Audit,
    SA8000CorrectiveAction,
    SA8000Document,
    SA8000NonConformity,
    SA8000Report,
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


sa8000_bp = Blueprint("sa8000", __name__, url_prefix="/sa8000")


def owner_only():
    if not current_user.is_owner:
        abort(403)


def _parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


@sa8000_bp.route("/")
@login_required
def dashboard():
    owner_only()
    open_reports = SA8000Report.query.filter(SA8000Report.status != "chiusa").order_by(SA8000Report.created_at.desc()).all()
    open_ncs = SA8000NonConformity.query.filter(SA8000NonConformity.status != "chiusa").order_by(SA8000NonConformity.created_at.desc()).all()
    recent_audits = SA8000Audit.query.order_by(SA8000Audit.audit_date.desc()).limit(5).all()
    today = date.today()
    return render_template(
        "sa8000/dashboard.html",
        open_reports=open_reports,
        open_ncs=open_ncs,
        recent_audits=recent_audits,
        categories=REPORT_CATEGORIES,
        today=today,
    )


@sa8000_bp.post("/segnalazioni")
@login_required
def create_report():
    owner_only()
    report = SA8000Report(
        category=request.form.get("category", "altro"),
        description=request.form.get("description", "").strip(),
        anonymous=request.form.get("anonymous") == "on",
        reporter_name=(request.form.get("reporter_name") or "").strip() or None,
    )
    if not report.description:
        flash("Descrivi la segnalazione prima di salvarla.", "error")
        return redirect(url_for("sa8000.dashboard"))
    db.session.add(report)
    db.session.commit()
    flash("Segnalazione registrata.", "success")
    return redirect(url_for("sa8000.dashboard"))


@sa8000_bp.post("/segnalazioni/<int:report_id>/stato")
@login_required
def update_report_status(report_id):
    owner_only()
    report = db.get_or_404(SA8000Report, report_id)
    status = request.form.get("status", "in_istruttoria")
    report.status = status
    if status == "chiusa":
        report.resolution_text = request.form.get("resolution_text", report.resolution_text)
        report.closed_at = datetime.utcnow()
    db.session.commit()
    flash("Segnalazione aggiornata.", "success")
    return redirect(url_for("sa8000.dashboard"))


@sa8000_bp.route("/non-conformita")
@login_required
def non_conformities():
    owner_only()
    ncs = SA8000NonConformity.query.order_by(SA8000NonConformity.created_at.desc()).all()
    today = date.today()
    return render_template("sa8000/non_conformita.html", ncs=ncs, today=today)


@sa8000_bp.post("/non-conformita")
@login_required
def create_non_conformity():
    owner_only()
    nc = SA8000NonConformity(
        clause=request.form.get("clause", "").strip(),
        description=request.form.get("description", "").strip(),
        severity=request.form.get("severity", "media"),
    )
    if not nc.clause or not nc.description:
        flash("Indica il requisito SA8000 e la descrizione della non conformità.", "error")
        return redirect(url_for("sa8000.non_conformities"))
    db.session.add(nc)
    db.session.commit()
    flash("Non conformità registrata.", "success")
    return redirect(url_for("sa8000.non_conformities"))


@sa8000_bp.post("/non-conformita/<int:nc_id>/chiudi")
@login_required
def close_non_conformity(nc_id):
    owner_only()
    nc = db.get_or_404(SA8000NonConformity, nc_id)
    nc.status = "chiusa"
    nc.closed_at = datetime.utcnow()
    db.session.commit()
    flash("Non conformità chiusa.", "success")
    return redirect(url_for("sa8000.non_conformities"))


@sa8000_bp.post("/non-conformita/<int:nc_id>/azioni")
@login_required
def create_action(nc_id):
    owner_only()
    nc = db.get_or_404(SA8000NonConformity, nc_id)
    action = SA8000CorrectiveAction(
        non_conformity_id=nc.id,
        description=request.form.get("description", "").strip(),
        responsible=request.form.get("responsible", "").strip() or None,
        due_date=_parse_date(request.form.get("due_date")),
    )
    if not action.description:
        flash("Descrivi l'azione correttiva.", "error")
        return redirect(url_for("sa8000.non_conformities"))
    if nc.status == "aperta":
        nc.status = "in_corso"
    db.session.add(action)
    db.session.commit()
    flash("Azione correttiva aggiunta.", "success")
    return redirect(url_for("sa8000.non_conformities"))


@sa8000_bp.post("/azioni/<int:action_id>/completa")
@login_required
def complete_action(action_id):
    owner_only()
    action = db.get_or_404(SA8000CorrectiveAction, action_id)
    action.status = request.form.get("status", "completata")
    if action.status in ("completata", "verificata_efficace"):
        action.completed_at = datetime.utcnow()
    db.session.commit()
    flash("Azione correttiva aggiornata.", "success")
    return redirect(url_for("sa8000.non_conformities"))


@sa8000_bp.route("/audit")
@login_required
def audits():
    owner_only()
    items = SA8000Audit.query.order_by(SA8000Audit.audit_date.desc()).all()
    return render_template("sa8000/audit.html", audits=items)


@sa8000_bp.post("/audit")
@login_required
def create_audit():
    owner_only()
    audit = SA8000Audit(
        audit_date=_parse_date(request.form.get("audit_date")) or date.today(),
        audit_type=request.form.get("audit_type", "interno"),
        auditor_name=request.form.get("auditor_name", "").strip() or None,
        scope=request.form.get("scope", "").strip() or None,
        outcome_summary=request.form.get("outcome_summary", "").strip() or None,
    )
    db.session.add(audit)
    db.session.commit()
    flash("Audit registrato.", "success")
    return redirect(url_for("sa8000.audits"))


@sa8000_bp.route("/documenti")
@login_required
def documents():
    owner_only()
    category = request.args.get("categoria", "")
    query = SA8000Document.query
    if category:
        query = query.filter_by(category=category)
    docs = query.order_by(SA8000Document.category, SA8000Document.code, SA8000Document.title).all()
    return render_template("sa8000/documenti.html", docs=docs, selected_category=category)


@sa8000_bp.route("/documenti/<int:doc_id>/scarica")
@login_required
def download_document(doc_id):
    owner_only()
    doc = db.get_or_404(SA8000Document, doc_id)
    return send_from_directory(current_app.static_folder, doc.file_path, as_attachment=True)


@sa8000_bp.route("/documenti/<int:doc_id>/visualizza")
@login_required
def view_document(doc_id):
    owner_only()
    doc = db.get_or_404(SA8000Document, doc_id)
    abs_path = os.path.join(current_app.static_folder, doc.file_path)
    html = document_to_html(abs_path)
    return render_template("sa8000/visualizza.html", doc=doc, html=html)


@sa8000_bp.post("/documenti/<int:doc_id>/compila")
@login_required
def start_compilation(doc_id):
    owner_only()
    doc = db.get_or_404(SA8000Document, doc_id)
    abs_path = os.path.join(current_app.static_folder, doc.file_path)
    html = document_to_html(abs_path)
    if html is None:
        flash("Questo documento non e' ancora convertito in formato compilabile.", "error")
        return redirect(url_for("sa8000.documents"))
    title = f"{doc.code} — {doc.title}" if doc.code else doc.title
    compiled = CompiledModule(domain="sa8000", source_document_id=doc.id, source_title=title, content_html=html)
    db.session.add(compiled)
    db.session.flush()
    _initialize_structured_fields(compiled)
    db.session.commit()
    return redirect(url_for("sa8000.edit_compilation", compilation_id=compiled.id))


@sa8000_bp.route("/compilazioni")
@login_required
def compilations():
    owner_only()
    items = CompiledModule.query.filter_by(domain="sa8000").order_by(CompiledModule.updated_at.desc()).all()
    return render_template("sa8000/compilazioni.html", items=items)


@sa8000_bp.route("/compilazioni/<int:compilation_id>")
@login_required
def edit_compilation(compilation_id):
    owner_only()
    compiled = db.get_or_404(CompiledModule, compilation_id)
    if compiled.domain != "sa8000":
        abort(404)
    if not compiled.fields:
        _initialize_structured_fields(compiled); db.session.commit()
    return render_template("sa8000/compila.html", compiled=compiled)


@sa8000_bp.post("/compilazioni/<int:compilation_id>")
@login_required
def save_compilation(compilation_id):
    owner_only()
    compiled = db.get_or_404(CompiledModule, compilation_id)
    if compiled.domain != "sa8000":
        abort(404)
    _save_structured_fields(compiled)
    db.session.commit()
    flash("Compilazione salvata.", "success")
    return redirect(url_for("sa8000.edit_compilation", compilation_id=compiled.id))


@sa8000_bp.post("/compilazioni/<int:compilation_id>/stato")
@login_required
def update_compilation_status(compilation_id):
    owner_only()
    compiled = db.get_or_404(CompiledModule, compilation_id)
    if compiled.domain != "sa8000":
        abort(404)
    compiled.status = "completato" if compiled.status != "completato" else "bozza"
    db.session.commit()
    return redirect(url_for("sa8000.compilations"))


@sa8000_bp.route("/compilazioni/<int:compilation_id>/stampa")
@login_required
def print_compilation(compilation_id):
    owner_only()
    compiled = db.get_or_404(CompiledModule, compilation_id)
    if compiled.domain != "sa8000":
        abort(404)
    return render_template("sa8000/stampa.html", compiled=compiled)

# --- Registro operativo unificato: filtro, modifica, cancellazione, evidenze ---
@sa8000_bp.route("/registro")
@login_required
def register():
    owner_only()
    from ..models_sa8000 import SA8000Evidence
    kind = request.args.get("tipo", "segnalazioni")
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("stato") or "").strip()
    models = {"segnalazioni": SA8000Report, "non_conformita": SA8000NonConformity,
              "audit": SA8000Audit, "azioni": SA8000CorrectiveAction}
    kind = kind if kind in models else "segnalazioni"
    model = models[kind]; query = model.query
    if q:
        cols = {"segnalazioni":[SA8000Report.description,SA8000Report.reporter_name],
                "non_conformita":[SA8000NonConformity.clause,SA8000NonConformity.description],
                "audit":[SA8000Audit.auditor_name,SA8000Audit.scope],
                "azioni":[SA8000CorrectiveAction.description,SA8000CorrectiveAction.responsible]}[kind]
        query = query.filter(db.or_(*[c.ilike(f"%{q}%") for c in cols]))
    if status and hasattr(model, "status"): query = query.filter(model.status == status)
    items = query.order_by(model.id.desc()).all()
    evidence = SA8000Evidence.query.filter_by(entity_type=kind).order_by(SA8000Evidence.uploaded_at.desc()).all()
    return render_template("sa8000/registro.html", kind=kind, items=items, evidence=evidence, q=q, status=status)

@sa8000_bp.post("/registro/<kind>/<int:item_id>/modifica")
@login_required
def register_edit(kind,item_id):
    owner_only()
    models={"segnalazioni":SA8000Report,"non_conformita":SA8000NonConformity,"audit":SA8000Audit,"azioni":SA8000CorrectiveAction}
    model=models.get(kind); item=db.get_or_404(model,item_id) if model else abort(404)
    allowed={"segnalazioni":["category","description","reporter_name","status","resolution_text"],
             "non_conformita":["clause","description","severity","status","root_cause"],
             "audit":["audit_type","auditor_name","scope","outcome_summary"],
             "azioni":["description","responsible","status"]}[kind]
    for field in allowed:
        if field in request.form: setattr(item,field,(request.form[field].strip() or None))
    if hasattr(item,"description") and not item.description:
        flash("La descrizione è obbligatoria.","error")
    else: db.session.commit(); flash("Voce aggiornata.","success")
    return redirect(url_for("sa8000.register",tipo=kind))

@sa8000_bp.post("/registro/<kind>/<int:item_id>/elimina")
@login_required
def register_delete(kind,item_id):
    owner_only()
    from ..models_sa8000 import SA8000Evidence
    from ..upload_tools import remove_upload
    models={"segnalazioni":SA8000Report,"non_conformita":SA8000NonConformity,"audit":SA8000Audit,"azioni":SA8000CorrectiveAction}
    model=models.get(kind); item=db.get_or_404(model,item_id) if model else abort(404)
    for ev in SA8000Evidence.query.filter_by(entity_type=kind,entity_id=item_id).all(): remove_upload(ev.file_path);db.session.delete(ev)
    if kind == "non_conformita":
        for action in item.actions: db.session.delete(action)
    db.session.delete(item);db.session.commit();flash("Voce eliminata.","success")
    return redirect(url_for("sa8000.register",tipo=kind))

@sa8000_bp.post("/registro/<kind>/<int:item_id>/evidenze")
@login_required
def register_evidence(kind,item_id):
    owner_only()
    from ..models_sa8000 import SA8000Evidence
    from ..upload_tools import save_upload
    try:
        title=(request.form.get("title") or "").strip()
        if not title: raise ValueError("Il titolo dell'evidenza è obbligatorio.")
        path=save_upload(request.files.get("file"),"sa8000")
        db.session.add(SA8000Evidence(entity_type=kind,entity_id=item_id,title=title,note=(request.form.get("note") or "").strip() or None,file_path=path));db.session.commit();flash("Evidenza caricata.","success")
    except ValueError as e: db.session.rollback();flash(str(e),"error")
    return redirect(url_for("sa8000.register",tipo=kind))

@sa8000_bp.post("/evidenze/<int:evidence_id>/elimina")
@login_required
def delete_evidence(evidence_id):
    owner_only();from ..models_sa8000 import SA8000Evidence;from ..upload_tools import remove_upload
    ev=db.get_or_404(SA8000Evidence,evidence_id);kind=ev.entity_type;remove_upload(ev.file_path);db.session.delete(ev);db.session.commit();flash("Evidenza eliminata.","success");return redirect(url_for("sa8000.register",tipo=kind))

@sa8000_bp.post("/documenti/carica")
@login_required
def upload_document():
    owner_only();from ..upload_tools import save_upload
    try:
        title=(request.form.get("title") or "").strip()
        if not title: raise ValueError("Il titolo è obbligatorio.")
        path=save_upload(request.files.get("file"),"sa8000")
        db.session.add(SA8000Document(category=request.form.get("category","allegato"),code=(request.form.get("code") or "").strip() or None,title=title,file_path=path));db.session.commit();flash("Documento caricato.","success")
    except ValueError as e:db.session.rollback();flash(str(e),"error")
    return redirect(url_for("sa8000.documents"))

@sa8000_bp.post("/documenti/<int:doc_id>/elimina")
@login_required
def delete_document(doc_id):
    owner_only();from ..upload_tools import remove_upload
    doc=db.get_or_404(SA8000Document,doc_id);remove_upload(doc.file_path);db.session.delete(doc);db.session.commit();flash("Documento eliminato.","success");return redirect(url_for("sa8000.documents"))

@sa8000_bp.post("/documenti/<int:doc_id>/modifica")
@login_required
def edit_document(doc_id):
    owner_only();doc=db.get_or_404(SA8000Document,doc_id);title=(request.form.get("title") or "").strip()
    if not title:flash("Il titolo è obbligatorio.","error")
    else:doc.title=title;doc.code=(request.form.get("code") or "").strip() or None;doc.category=request.form.get("category",doc.category);db.session.commit();flash("Documento aggiornato.","success")
    return redirect(url_for("sa8000.documents"))
