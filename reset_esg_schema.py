"""Migrazione una tantum per lo schema ESG.

Il modulo ESG e' stato sostituito con un impianto piu' completo (rapporti annuali
con sezioni, KPI, temi, piano, stakeholder, approvazioni). Le tabelle vecchie
(esg_report con schema precedente, esg_indicator, esg_measurement, esg_target)
non vengono aggiornate automaticamente da SQLAlchemy: create_all() crea solo
le tabelle mancanti, non altera quelle esistenti con schema diverso.

Questo script verifica se la tabella esg_report esiste ancora con lo schema
vecchio (manca la colonna "title", presente solo nel nuovo modello) e in tal
caso la rimuove insieme alle altre tabelle ESG obsolete, cosi' il prossimo
db.create_all() (eseguito automaticamente da create_app()) la ricrea pulita
con lo schema nuovo. E' idempotente: se lo schema e' gia' aggiornato, o se le
tabelle non esistono ancora, non fa nulla.
"""

from sqlalchemy import inspect, text

from app import create_app
from app.extensions import db

OLD_TABLES = ("esg_target", "esg_measurement", "esg_indicator", "esg_report")


def _needs_reset(inspector):
    if "esg_report" not in inspector.get_table_names():
        return False
    columns = {c["name"] for c in inspector.get_columns("esg_report")}
    return "title" not in columns


def reset_if_needed():
    app = create_app()
    with app.app_context():
        inspector = inspect(db.engine)
        if not _needs_reset(inspector):
            print("Schema ESG gia' aggiornato: nessuna migrazione necessaria.")
            return
        dialect = db.engine.dialect.name
        with db.engine.begin() as conn:
            for table in OLD_TABLES:
                suffix = " CASCADE" if dialect == "postgresql" else ""
                conn.execute(text(f"DROP TABLE IF EXISTS {table}{suffix}"))
        print("Schema ESG obsoleto rimosso: verra' ricreato pulito al prossimo avvio.")


if __name__ == "__main__":
    reset_if_needed()
