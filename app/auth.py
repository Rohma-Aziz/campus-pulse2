import re
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from app import db
from app.models import DEPARTMENTS, User

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        department = request.form.get("department", "").strip()
        year_val = request.form.get("year", "").strip()

        # Check password match
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("signup.html", DEPARTMENTS=DEPARTMENTS)

        # Validate minimum length
        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "danger")
            return render_template("signup.html", DEPARTMENTS=DEPARTMENTS)

        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email address is already registered. Please login.", "warning")
            return redirect(url_for("auth.login"))

        # Convert year to int if provided, else None
        year = int(year_val) if year_val.isdigit() else None

        # Create new student user
        new_user = User(
            name=name,
            email=email,
            role="student",
            department=department,
            year=year
        )
        new_user.set_password(password)

        try:
            db.session.add(new_user)
            db.session.commit()
            flash("Account created successfully! Please log in with your credentials.", "success")
            return redirect(url_for("auth.login"))
        except Exception as e:
            db.session.rollback()
            flash("An error occurred while creating your account. Please try again.", "danger")
            return render_template("signup.html", DEPARTMENTS=DEPARTMENTS)
        
    return render_template("signup.html", DEPARTMENTS=DEPARTMENTS)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email").strip().lower()
        password = request.form.get("password")
        selected_role = request.form.get("role")  # 'student' ya 'admin'

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            # Role validation check
            if selected_role == "admin" and not user.is_admin:
                flash("Access denied. This account is not registered as an Admin.", "danger")
                return redirect(url_for("auth.login"))
            
            if selected_role == "student" and user.is_admin:
                flash("Please select Admin role to login with this account.", "danger")
                return redirect(url_for("auth.login"))

            session.clear()
            session["user_id"] = user.id
            
            flash("Logged in successfully!", "success")
            
            # Role ke mutabiq redirect karein
            if user.is_admin:
                return redirect(url_for("admin.dashboard"))
            else:
                return redirect(url_for("feedback.dashboard"))
        
        flash("Invalid email or password.", "danger")
        
    return render_template("login.html")


@auth_bp.route("/logout", methods=["GET","POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@auth_bp.route('/dashboard')
def profile():
    if not g.user:
        flash("Please log in to view your dashboard.", "warning")
        return redirect(url_for("auth.login"))
    return render_template('profile.html', user=g.user)