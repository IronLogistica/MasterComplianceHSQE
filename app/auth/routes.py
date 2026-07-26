from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from ..models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.board"))
    if request.method == "POST":
        user = User.query.filter_by(pin=request.form.get("pin", ""), active=True).first()
        if user:
            login_user(user)
            return redirect(url_for("dashboard.board") if user.is_owner else url_for("work.my_work"))
        flash("PIN non riconosciuto.", "error")
    return render_template("auth/login.html")


@auth_bp.post("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
