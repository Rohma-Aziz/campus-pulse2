import re

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from app import db
from app.models import DEPARTMENTS, User

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    """Student sign up only. Admin accounts are created with the create-admin command."""
    if g.user:
        return redirect(url_for("home"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        department = request.form.get("department")
        year = request.form.get("year", type=int)

        error = None
        if not 2 <= len(name) <= 100:
            error = "Please enter your name."
        elif not EMAIL_RE.match(email) or len(email) > 120:
            error = "Please enter a valid email."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif department not in DEPARTMENTS:
            error = "Please choose a department."
        elif year is not None and not 1 <= year <= 4:
            error = "Year must be between 1 and 4."
        elif User.query.filter_by(email=email).first():
            error = "An account with that email already exists."

        if error:
            flash(error, "danger")
        else:
            user = User(name=name, email=email, department=department, year=year, role="student")
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("Account created. Please log in.", "success")
            return redirect(url_for("auth.login"))

    return render_template("signup.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("home"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            session.clear()  # prevents session fixation
            session["user_id"] = user.id
            return redirect(url_for("home"))  # role check happens in home()

        flash("Invalid email or password.", "danger")  # same message for both cases

    return render_template("login.html")


@auth_bp.post("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))