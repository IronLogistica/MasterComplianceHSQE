"""Gestione centralizzata e prudente degli allegati."""
import os
from uuid import uuid4
from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"pdf","png","jpg","jpeg","webp","doc","docx","xls","xlsx","csv","txt","odt"}
MAX_UPLOAD = 16 * 1024 * 1024

def save_upload(storage, area):
    if not storage or not storage.filename:
        raise ValueError("Seleziona un file da allegare.")
    original = secure_filename(storage.filename)
    if not original or "." not in original:
        raise ValueError("Nome file non valido.")
    ext = original.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Formato file non consentito.")
    storage.stream.seek(0, 2); size = storage.stream.tell(); storage.stream.seek(0)
    if size > MAX_UPLOAD:
        raise ValueError("Il file supera il limite di 16 MB.")
    name = f"{uuid4().hex}-{original}"
    relative = os.path.join("uploads", area, name).replace(os.sep, "/")
    directory = os.path.join(current_app.static_folder, "uploads", area)
    os.makedirs(directory, exist_ok=True)
    storage.save(os.path.join(directory, name))
    return relative

def remove_upload(relative):
    if not relative or not relative.startswith("uploads/"): return
    path = os.path.abspath(os.path.join(current_app.static_folder, relative))
    root = os.path.abspath(os.path.join(current_app.static_folder, "uploads"))
    if path.startswith(root + os.sep) and os.path.isfile(path): os.remove(path)
