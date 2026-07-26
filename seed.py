from datetime import date, timedelta

from app import create_app
from app.extensions import db
from app.models import (
    ControlType,
    Job,
    Machine,
    MaintenancePlan,
    PPEIssue,
    PPEItem,
    QualityPlan,
    Site,
    SiteWorker,
    Technician,
    TrainingCourse,
    TrainingRecord,
    User,
)

app = create_app()
with app.app_context():
    if not Machine.query.first():
        tecnico = Technician(name="Tecnico Interno")
        db.session.add(tecnico)
        db.session.flush()
        controllo_ordinario = ControlType(name="Manutenzione ordinaria")
        controllo_taratura = ControlType(name="Taratura strumento")
        db.session.add_all([controllo_ordinario, controllo_taratura])
        db.session.flush()
        pressa = Machine(code="MAC-001", name="Pressa piegatrice", default_technician_id=tecnico.id)
        saldatrice = Machine(code="MAC-002", name="Saldatrice a filo", default_technician_id=tecnico.id)
        db.session.add_all([pressa, saldatrice])
        db.session.flush()
        db.session.add_all([
            MaintenancePlan(machine_id=pressa.id, control_type_id=controllo_ordinario.id, technician_id=tecnico.id, frequency_days=90, next_due=date.today() + timedelta(days=5)),
            MaintenancePlan(machine_id=saldatrice.id, control_type_id=controllo_taratura.id, technician_id=tecnico.id, frequency_days=180, next_due=date.today() + timedelta(days=2)),
        ])
        db.session.commit()
        print("Dati demo manutenzione creati.")

    if not User.query.first():
        db.session.add_all([
            User(name="Titolare", pin="9999", role="owner"),
            User(name="Marco Rossi", pin="1234", role="operator"),
            User(name="Luca Bianchi", pin="5678", role="operator"),
        ])
        db.session.add_all([
            Job(code="ODL-2026-001", article_code="STA-1842", article_name="Staffa supporto", phase="Saldatura", planned_qty=300, priority="alta", quality_plan_ref="CPC-1842 rev. 03"),
            Job(code="ODL-2026-002", article_code="FOR-810", article_name="Flangia forata", phase="Controllo finale", planned_qty=120, priority="normale", quality_plan_ref="CPC-810 rev. 01"),
            Job(code="ODL-2026-003", article_code="PIA-255", article_name="Piastra base", phase="Piegatura", planned_qty=80, priority="normale"),
        ])
        db.session.add(QualityPlan(article_code="STA-1842", revision="03", first_piece_required=True, controls_text="Primo pezzo; controllo visivo ogni 50 pezzi; dimensione ogni lotto."))
        db.session.commit()
        print("Dati demo creati.")
    else:
        print("Database già popolato: nessuna modifica.")

    if not TrainingCourse.query.first():
        formazione_generale = TrainingCourse(name="Formazione generale lavoratori", category="Formazione generale")
        formazione_specifica = TrainingCourse(name="Formazione specifica rischio alto", category="Formazione specifica", validity_months=60, required_for_site=True)
        antincendio = TrainingCourse(name="Addetto antincendio rischio medio", category="Antincendio", validity_months=36, required_for_site=True)
        primo_soccorso = TrainingCourse(name="Addetto primo soccorso", category="Primo soccorso", validity_months=36, required_for_site=True)
        db.session.add_all([formazione_generale, formazione_specifica, antincendio, primo_soccorso])
        db.session.flush()

        casco = PPEItem(name="Casco di protezione", category="II", required_for_site=True)
        alta_visibilita = PPEItem(name="Giubbotto alta visibilità", category="II", replacement_months=24, required_for_site=True)
        scarpe = PPEItem(name="Scarpe antinfortunistiche", category="II", replacement_months=18)
        db.session.add_all([casco, alta_visibilita, scarpe])
        db.session.flush()

        marco = User.query.filter_by(name="Marco Rossi").first()
        luca = User.query.filter_by(name="Luca Bianchi").first()
        oggi = date.today()

        if marco:
            # Marco è in regola con tutto: idoneo per il cantiere
            db.session.add_all([
                TrainingRecord(worker_id=marco.id, course_id=formazione_generale.id, completed_on=oggi - timedelta(days=200)),
                TrainingRecord(worker_id=marco.id, course_id=formazione_specifica.id, completed_on=oggi - timedelta(days=200), expires_on=oggi + timedelta(days=1400)),
                TrainingRecord(worker_id=marco.id, course_id=antincendio.id, completed_on=oggi - timedelta(days=200), expires_on=oggi + timedelta(days=880)),
                TrainingRecord(worker_id=marco.id, course_id=primo_soccorso.id, completed_on=oggi - timedelta(days=200), expires_on=oggi + timedelta(days=880)),
            ])
            db.session.add_all([
                PPEIssue(worker_id=marco.id, ppe_item_id=casco.id, issued_on=oggi - timedelta(days=100)),
                PPEIssue(worker_id=marco.id, ppe_item_id=alta_visibilita.id, issued_on=oggi - timedelta(days=100), expires_on=oggi + timedelta(days=630)),
            ])

        if luca:
            # Luca ha solo la formazione generale: NON idoneo per il cantiere (mancano corsi e DPI obbligatori)
            db.session.add(TrainingRecord(worker_id=luca.id, course_id=formazione_generale.id, completed_on=oggi - timedelta(days=60)))

        cantiere = Site(
            name="Segnaletica SS45 — Comune di Città di Castello",
            client_name="Comune di Città di Castello",
            address="SS45, Città di Castello (PG)",
            start_date=oggi + timedelta(days=10),
            end_date=oggi + timedelta(days=40),
        )
        db.session.add(cantiere)
        db.session.flush()
        if marco:
            db.session.add(SiteWorker(site_id=cantiere.id, worker_id=marco.id))
        if luca:
            db.session.add(SiteWorker(site_id=cantiere.id, worker_id=luca.id))

        db.session.commit()
        print("Dati demo sicurezza creati (1 operaio idoneo, 1 non idoneo per test).")
