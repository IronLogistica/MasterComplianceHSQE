import csv
from datetime import datetime
from io import StringIO
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for, Response
from flask_login import current_user, login_required
from ..extensions import db
from ..models_esg import (ESGReport, ESGMetric, ESGSectionContent, ESGTopic, ESGActionPlan,
                      ESGStakeholderEngagement, ESGProcessIntegration, ESGApproval)

esg_bp = Blueprint("esg", __name__, url_prefix="/esg")
STATUS = ("bozza", "raccolta_dati", "in_revisione", "restituito", "approvato", "pubblicato")
SECTIONS = [
 ("commitment", "Impegno della direzione"), ("organization", "1. Organizzazione e criteri di rendicontazione"),
 ("value_chain", "2. Attività, modello operativo e catena del valore"), ("people", "3. Persone e lavoro nella catena del valore"),
 ("governance", "4. Governance e condotta d'impresa"), ("strategy", "5. Strategia, policy e temi materiali"),
 ("results", "6. Risultati dell'esercizio: azioni, KPI e target"), ("integration", "7. Integrazione ESG nei processi di gestione"),
 ("plan", "8. Piano di miglioramento dell'esercizio successivo"), ("policies", "Allegato A — Policy"),
 ("index", "Allegato B — Indice di contenuti e riferimenti"), ("methodology", "Allegato C — Metodologia e glossario"),
 ("approval", "Approvazione e firme")]

def owner():
    if not current_user.is_authenticated or not current_user.is_owner: abort(403)
def text(k): return request.form.get(k, "").strip() or None
def number(k):
    raw=text(k)
    if not raw: return None
    try: return float(raw.replace(",", "."))
    except ValueError: raise ValueError("I valori KPI devono essere numerici.")
def get_report(rid): return db.get_or_404(ESGReport, rid)
def editable(r):
    if r.status in ("approvato", "pubblicato"):
        raise ValueError("Il rapporto è approvato/pubblicato: riaprirlo prima di modificare i contenuti.")
def placeholder(): return bool(request.form.get("is_placeholder"))

def seed_report(r):
    editable(r)
    if r.sections: return False
    generic = {
      "commitment":"La Direzione di [RAGIONE SOCIALE] considera risultati durevoli, persone, risorse e integrità come elementi interdipendenti. Questo rapporto descrive dati disponibili, priorità e prossimi passi e sarà riesaminato con cadenza [FREQUENZA].",
      "organization":"Il documento definisce perimetro, periodo, fonti e limiti della rendicontazione. Le informazioni devono essere confermate dall'organizzazione prima dell'approvazione.",
      "value_chain":"La mappa di filiera deve identificare fasi a monte, operazioni proprie e fasi a valle, con rischi, impatti e leve di influenza proporzionate.",
      "people":"L'organizzazione monitora condizioni di lavoro, competenze, sicurezza e inclusione. Gli indicatori sono da completare con definizioni, copertura e limiti.",
      "governance":"Ruoli, deleghe, codice etico, canali di segnalazione e controlli devono essere descritti in base agli assetti effettivamente adottati.",
      "strategy":"La priorità dei temi deriva da dialogo con stakeholder, analisi di impatti e rischi/opportunità. I temi sotto riportati sono candidati e non sono già approvati.",
      "results":"Per ogni tema materiale occorre indicare KPI, confronto, metodologia, fonte, azioni, scostamenti e prossimi passi; ND non equivale a zero.",
      "integration":"I presidi ESG si integrano nei processi di acquisto, persone, sicurezza, ambiente, progetti, amministrazione e riesame direzionale.",
      "plan":"Gli obiettivi devono essere SMART, con baseline, responsabile, risorse, scadenza e verifica documentata.",
      "policies":"Inserire qui policy ESG o il riferimento al documento controllato approvato dall'organizzazione.",
      "index":"Riferimenti GRI o altri standard sono una mappa selezionata; non dichiarano conformità senza una verifica applicabile.",
      "methodology":"Definire confini, formule, basi di intensità, fonti, qualità dei dati, fattori di conversione, rettifiche e glossario.",
      "approval":"L'approvazione nell'app è una registrazione interna. Per esigenze di firma elettronica o legale usare il processo esterno adottato dal cliente."}
    for n,(code,title) in enumerate(SECTIONS): db.session.add(ESGSectionContent(report_id=r.id,section_code=code,title=title,body=generic[code],is_placeholder=True,sort_order=n))
    topics=[("E.ENERGY","Efficienza nell'uso di energia e risorse","E"),("S.SAFETY","Salute, sicurezza e benessere","S"),("S.WORK","Competenze e lavoro dignitoso","S"),("G.ETHICS","Integrità, etica e catena responsabile","G")]
    for n,(code,title,p) in enumerate(topics): db.session.add(ESGTopic(report_id=r.id,code=code,title=title,pillar=p,description="Tema candidato da valutare con stakeholder e analisi documentata.",priority_level="da valutare",is_placeholder=True,sort_order=n))
    catalog=[("E","E.ENERGY.ELECTRICITY","Elettricità acquistata","kWh"),("E","E.ENERGY.FUELS","Combustibili per tipo","kWh o litri"),("E","E.GHG.S1","Emissioni Scope 1","tCO2e"),("E","E.GHG.S2","Emissioni Scope 2","tCO2e"),("E","E.WATER","Prelievo idrico","m³"),("E","E.WASTE","Rifiuti prodotti","kg"),("S","S.WORKFORCE.FTE","FTE medi","FTE"),("S","S.TRAIN.HOURS","Ore di formazione","ore"),("S","S.HS.HOURS","Ore lavorate","ore"),("S","S.HS.INCIDENTS","Infortuni registrabili","numero"),("S","S.HS.LTIFR","Tasso infortuni","per 1.000.000 ore"),("S","S.GRIEVANCES","Segnalazioni aggregate","numero"),("G","G.ESG.GOVERNANCE","Riesami ESG","numero"),("G","G.ETHICS.TRAINING","Formazione etica completata","%"),("G","G.SUPPLIERS.ESG_SCREENED","Fornitori critici valutati ESG","%"),("G","G.WHISTLEBLOWING","Segnalazioni whistleblowing aggregate","numero")]
    for n,(p,c,name,u) in enumerate(catalog): db.session.add(ESGMetric(report_id=r.id,pillar=p,code=c,name=name,unit=u,data_quality="ND",methodology="DA PERSONALIZZARE — definire metodo e perimetro",source_ref="DA PERSONALIZZARE — indicare evidenza",note="Dato non disponibile: completare o motivare.",is_placeholder=True,sort_order=n))
    for category in ("Persone e lavoratori", "Clienti e utilizzatori", "Fornitori e partner", "Comunità e istituzioni"):
        db.session.add(ESGStakeholderEngagement(report_id=r.id,category=category,channel="DA PERSONALIZZARE",period="DA PERSONALIZZARE",expectations="Raccogliere aspettative e temi rilevanti.",response="Restituire esiti e azioni.",is_placeholder=True))
    for proc in ("Acquisti", "Persone e formazione", "Salute, sicurezza e ambiente", "Riesame direzionale"):
        db.session.add(ESGProcessIntegration(report_id=r.id,process=proc,owner="DA PERSONALIZZARE",control="Definire presidio ESG e controllo.",frequency="DA PERSONALIZZARE",evidence_ref="DA PERSONALIZZARE",outcome="Da verificare",is_placeholder=True))
    for title, kpi in (("Definire priorità ESG", "G.ESG.GOVERNANCE"),("Migliorare la qualità dei dati", "G.DATA_QUALITY"),("Valutare efficienza delle risorse", "E.ENERGY.ELECTRICITY")):
        db.session.add(ESGActionPlan(report_id=r.id,title=title,objective="DA PERSONALIZZARE — definire un obiettivo SMART",kpi_code=kpi,baseline="ND",target="DA PERSONALIZZARE",responsible="DA PERSONALIZZARE",status="pianificato",verification="DA PERSONALIZZARE",is_placeholder=True))
    return True

@esg_bp.route("/", methods=["GET","POST"])
@login_required
def reports():
    owner()
    if request.method == "POST":
        try:
            year=int(request.form.get("year",""));
            if not 2000 <= year <= 2100: raise ValueError("Inserisci un anno valido.")
            if ESGReport.query.filter_by(year=year).first(): raise ValueError("Esiste già un rapporto per questo anno.")
            r=ESGReport(year=year,title=text("title") or "Rapporto di sostenibilità",legal_name=text("legal_name"),report_type=text("report_type") or "Rapporto volontario ESG")
            db.session.add(r); db.session.flush()
            if request.form.get("seed"): seed_report(r)
            db.session.commit(); flash("Rapporto ESG creato.","success")
        except ValueError as e: db.session.rollback(); flash(str(e),"error")
        return redirect(url_for("esg.reports"))
    return render_template("esg/reports.html",items=ESGReport.query.order_by(ESGReport.year.desc()).all())

@esg_bp.post("/<int:report_id>/seed")
@login_required
def seed(report_id):
    owner(); r=get_report(report_id)
    try:
        if seed_report(r): db.session.commit(); flash("Baseline generico creato: ogni contenuto è DA PERSONALIZZARE.","success")
        else: flash("Il rapporto contiene già il baseline; nessun dato è stato sovrascritto.","error")
    except ValueError as e: flash(str(e),"error")
    return redirect(url_for("esg.dashboard",report_id=r.id))

@esg_bp.route("/<int:report_id>")
@login_required
def dashboard(report_id):
    owner(); r=get_report(report_id)
    return render_template("esg/report_dashboard.html",report=r,sections=SECTIONS, placeholders=sum(x.is_placeholder for x in r.sections)+sum(x.is_placeholder for x in r.metrics))

@esg_bp.route("/<int:report_id>/metadata",methods=["GET","POST"])
@login_required
def metadata(report_id):
    owner(); r=get_report(report_id)
    if request.method=="POST":
        try:
            editable(r)
            for f in ("title","legal_name","report_type","reporting_boundary","currency","reporting_framework","contact_email","methodology_note","management_statement","notes"): setattr(r,f,text(f))
            for f in ("reporting_period_start","reporting_period_end"):
                raw=text(f); setattr(r,f,datetime.strptime(raw,"%Y-%m-%d").date() if raw else None)
            db.session.commit();flash("Metadati aggiornati.","success")
        except ValueError as e: db.session.rollback();flash(str(e),"error")
        return redirect(url_for("esg.metadata",report_id=r.id))
    return render_template("esg/metadata.html",report=r)

@esg_bp.route("/<int:report_id>/sections/<code>",methods=["GET","POST"])
@login_required
def section(report_id,code):
    owner(); r=get_report(report_id); sec=ESGSectionContent.query.filter_by(report_id=r.id,section_code=code).first_or_404()
    if request.method=="POST":
        try:
            editable(r);sec.title=text("title") or sec.title;sec.body=text("body");sec.is_placeholder=placeholder();db.session.commit();flash("Sezione salvata.","success")
        except ValueError as e:flash(str(e),"error")
        return redirect(url_for("esg.section",report_id=r.id,code=code))
    return render_template("esg/section_editor.html",report=r,section=sec)

@esg_bp.route("/<int:report_id>/metrics",methods=["GET","POST"])
@login_required
def metrics(report_id):
    owner();r=get_report(report_id)
    if request.method=="POST":
        try:
            editable(r); p=text("pillar");
            if p not in ("E","S","G") or not text("name"): raise ValueError("Pilastro e nome sono obbligatori.")
            q=text("data_quality") or "ND"
            if q not in ("misurato","stimato","ND"): raise ValueError("Qualità dato non valida.")
            if q=="misurato" and (not text("methodology") or not text("source_ref")): raise ValueError("Un dato misurato richiede metodo e fonte/evidenza.")
            m=ESGMetric(report_id=r.id,pillar=p,code=text("code"),name=text("name"),value=number("value"),previous_value=number("previous_value"),baseline_value=number("baseline_value"),target_value=number("target_value"),unit=text("unit"),denominator_value=number("denominator_value"),denominator_unit=text("denominator_unit"),formula=text("formula"),data_quality=q,methodology=text("methodology"),source_ref=text("source_ref"),data_owner=text("data_owner"),note=text("note"),visible_in_report=bool(request.form.get("visible_in_report")),is_placeholder=placeholder())
            db.session.add(m);db.session.commit();flash("KPI aggiunto.","success")
        except ValueError as e:db.session.rollback();flash(str(e),"error")
        return redirect(url_for("esg.metrics",report_id=r.id))
    return render_template("esg/metrics.html",report=r,metrics=sorted(r.metrics,key=lambda x:(x.pillar,x.sort_order,x.name)))

@esg_bp.post("/metrics/<int:metric_id>/delete")
@login_required
def delete_metric(metric_id):
    owner();m=db.get_or_404(ESGMetric,metric_id)
    try: editable(m.report);db.session.delete(m);db.session.commit();flash("KPI eliminato.","success")
    except ValueError as e:flash(str(e),"error")
    return redirect(url_for("esg.metrics",report_id=m.report_id))

@esg_bp.route("/<int:report_id>/topics",methods=["GET","POST"])
@login_required
def topics(report_id):
    owner();r=get_report(report_id)
    if request.method=="POST":
        try:
            editable(r);p=text("pillar");
            if p not in ("E","S","G") or not text("title"): raise ValueError("Pilastro e titolo sono obbligatori.")
            db.session.add(ESGTopic(report_id=r.id,code=text("code") or "DA.PERSONALIZZARE",title=text("title"),pillar=p,description=text("description"),organization_score=number("organization_score"),stakeholder_score=number("stakeholder_score"),priority_level=text("priority_level"),owner=text("owner"),is_placeholder=placeholder()));db.session.commit();flash("Tema aggiunto.","success")
        except ValueError as e:db.session.rollback();flash(str(e),"error")
        return redirect(url_for("esg.topics",report_id=r.id))
    return render_template("esg/topics.html",report=r)

@esg_bp.route("/<int:report_id>/actions",methods=["GET","POST"])
@login_required
def actions(report_id):
    owner();r=get_report(report_id)
    if request.method=="POST":
        try:
            editable(r)
            if not text("title"):raise ValueError("Il titolo dell'azione è obbligatorio.")
            db.session.add(ESGActionPlan(report_id=r.id,title=text("title"),objective=text("objective"),kpi_code=text("kpi_code"),baseline=text("baseline"),target=text("target"),responsible=text("responsible"),status=text("status") or "pianificato",verification=text("verification"),is_placeholder=placeholder()));db.session.commit();flash("Azione aggiunta.","success")
        except ValueError as e: db.session.rollback();flash(str(e),"error")
        return redirect(url_for("esg.actions",report_id=r.id))
    return render_template("esg/actions.html",report=r)

@esg_bp.route("/<int:report_id>/engagement",methods=["GET","POST"])
@login_required
def engagement(report_id):
    owner(); r=get_report(report_id)
    if request.method == "POST":
        try:
            editable(r)
            kind=text("kind")
            if kind == "stakeholder":
                if not text("category"): raise ValueError("La categoria stakeholder è obbligatoria.")
                db.session.add(ESGStakeholderEngagement(report_id=r.id,category=text("category"),channel=text("channel"),period=text("period"),expectations=text("expectations"),response=text("response"),is_placeholder=placeholder()))
            else:
                if not text("process"): raise ValueError("Il processo è obbligatorio.")
                db.session.add(ESGProcessIntegration(report_id=r.id,process=text("process"),owner=text("owner"),control=text("control"),frequency=text("frequency"),evidence_ref=text("evidence_ref"),outcome=text("outcome"),is_placeholder=placeholder()))
            db.session.commit(); flash("Registro aggiornato.","success")
        except ValueError as e: db.session.rollback(); flash(str(e),"error")
        return redirect(url_for("esg.engagement",report_id=r.id))
    return render_template("esg/engagement.html",report=r)

@esg_bp.route("/<int:report_id>/approval",methods=["GET","POST"])
@login_required
def approval(report_id):
    owner();r=get_report(report_id)
    if request.method=="POST":
        role=text("role")
        if not role: flash("Indicare il ruolo dell'approvatore.","error")
        else:
            db.session.add(ESGApproval(report_id=r.id,role=role,signer_name=text("signer_name"),method=text("method") or "approvazione autenticata nell'app",decision=text("decision") or "approvato",statement_text=text("statement_text") or "Approvazione interna registrata."));r.status="approvato";r.version="1.0";db.session.commit();flash("Approvazione interna registrata.","success")
        return redirect(url_for("esg.approval",report_id=r.id))
    return render_template("esg/approval_page.html",report=r)

@esg_bp.get("/<int:report_id>/print")
@login_required
def report_print(report_id):
    owner();r=get_report(report_id); return render_template("esg/report_print.html",report=r,sections=SECTIONS)

@esg_bp.get("/<int:report_id>/export.csv")
@login_required
def export_csv(report_id):
    owner();r=get_report(report_id);out=StringIO();w=csv.writer(out);w.writerow(["codice","pilastro","nome","corrente","precedente","baseline","target","unita","qualita","metodo","fonte","placeholder"])
    for m in r.metrics:w.writerow([m.code,m.pillar,m.name,m.value,m.previous_value,m.baseline_value,m.target_value,m.unit,m.data_quality,m.methodology,m.source_ref,m.is_placeholder])
    return Response(out.getvalue(),mimetype="text/csv",headers={"Content-Disposition":f"attachment; filename=esg-kpi-{r.year}.csv"})
