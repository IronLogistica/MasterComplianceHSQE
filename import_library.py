"""Importa nel database i documenti della libreria SA8000 e ISO 14001 (ambiente).

Scansiona app/static/library/sa8000/<categoria>/ e app/static/library/ambiente/<categoria>/
e crea un record per ogni file trovato (idempotente: salta i file già importati,
riconosciuti dal file_path memorizzato). Va eseguito una volta e ad ogni deploy
(vedi Procfile) cosi' i nuovi documenti aggiunti alla libreria vengono importati
automaticamente senza intervento manuale.
"""

import os
import re

from app import create_app
from app.extensions import db
from app.models_environment import EnvironmentalDocument
from app.models_sa8000 import SA8000Document

CHAR_FIXES = {
    "#U00e0": "à", "#U00e8": "è", "#U00ec": "ì", "#U00f2": "ò", "#U00f9": "ù",
    "#U00c0": "À", "#U00c8": "È",
}

SA8000_CODE_RE = re.compile(r"^(PROC|MOD|ALL)-([0-9]+(?:-[0-9]+)?)[\s\-_]*(.*)$", re.IGNORECASE)
ISO_PR_CODE_RE = re.compile(r"^(PR)\s+([0-9]+(?:\.[0-9]+)*)[\s._-]*(.*)$", re.IGNORECASE)
ISO_MOD_CODE_RE = re.compile(r"^(Mod\.?|MOD\.?|M)\s*([0-9]+(?:\.[0-9]+)*)[\s.\-_]*(.*)$", re.IGNORECASE)
ISO_ALLEGATO_CODE_RE = re.compile(r"^(ALLEGATO)\s+([0-9]+)[\s\-_]*(.*)$", re.IGNORECASE)


def _clean_text(text):
    for bad, good in CHAR_FIXES.items():
        text = text.replace(bad, good)
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text).strip(" .-")
    return text or "Documento"


def _parse_name(stem):
    for pattern in (SA8000_CODE_RE, ISO_PR_CODE_RE, ISO_ALLEGATO_CODE_RE, ISO_MOD_CODE_RE):
        m = pattern.match(stem)
        if m:
            prefix, number, rest = m.group(1), m.group(2), m.group(3)
            code = f"{prefix.upper().rstrip('.')}-{number}" if prefix.upper().startswith(("PROC", "MOD", "ALL")) and "-" not in prefix else f"{prefix.strip('.').upper()} {number}"
            # normalizza codice ISO: "PR 8.1.1", SA8000: "PROC-940"
            if prefix.upper() in ("PROC", "MOD", "ALL"):
                code = f"{prefix.upper()}-{number}"
            elif prefix.upper() == "PR":
                code = f"PR {number}"
            elif prefix.upper() == "ALLEGATO":
                code = f"ALLEGATO {number}"
            else:  # Mod./MOD./M
                code = f"M{number}"
            return code, _clean_text(rest)
    return None, _clean_text(stem)


def _import_folder(static_dir, base_dir, category, model_cls):
    if not os.path.isdir(base_dir):
        return 0
    created = 0
    existing_paths = {p for (p,) in db.session.query(model_cls.file_path).all()}
    for filename in sorted(os.listdir(base_dir)):
        full_path = os.path.join(base_dir, filename)
        if not os.path.isfile(full_path):
            continue
        rel_path = os.path.relpath(full_path, start=static_dir).replace(os.sep, "/")
        if rel_path in existing_paths:
            continue
        stem, _ext = os.path.splitext(filename)
        code, title = _parse_name(stem)
        db.session.add(model_cls(category=category, code=code, title=title, file_path=rel_path))
        created += 1
    return created


def import_library():
    app = create_app()
    with app.app_context():
        static_dir = app.static_folder
        total = 0

        sa8000_root = os.path.join(static_dir, "library", "sa8000")
        for category, folder in (
            ("manuale", "manuale"),
            ("procedura", "procedure"),
            ("modulistica", "modulistica"),
            ("allegato", "allegati"),
        ):
            total += _import_folder(static_dir, os.path.join(sa8000_root, folder), category, SA8000Document)

        env_root = os.path.join(static_dir, "library", "ambiente")
        for category, folder in (
            ("manuale", "manuale"),
            ("procedura", "procedure"),
            ("modulo", "moduli"),
            ("allegato", "allegati"),
        ):
            total += _import_folder(static_dir, os.path.join(env_root, folder), category, EnvironmentalDocument)

        db.session.commit()
        if total:
            print(f"Libreria documentale: {total} nuovi documenti importati.")
        else:
            print("Libreria documentale: nessun nuovo documento da importare.")


if __name__ == "__main__":
    import_library()
