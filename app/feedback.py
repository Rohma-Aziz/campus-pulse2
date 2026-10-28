from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy import func, select

from app import db
from app.models import DEPARTMENTS, FEEDBACK_CATEGORIES, STATUSES, Feedback
from app.utils import admin_required, login_required

feedback_bp = Blueprint("feedback", __name__, url_prefix="/feedback")

TITLE_MIN, TITLE_MAX = 3, 150
DESC_MIN, DESC_MAX = 10, 2000
NOTE_MAX = 500
PER_PAGE = 10


def pick(value, allowed):
    """Return value only if it is an allowed choice (protects filters from bad input)."""
    return value if value in allowed else None


# ---------------------------------------------------------------- student side
@feedback_bp.route("/new", methods=["GET", "POST"])
@login_required
def submit():
    if g.user.is_admin:
        flash("Students submit feedback. Admins review it here.", "info")
        return redirect(url_for("feedback.manage"))

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        category = request.form.get("category")
        rating = request.form.get("rating", type=int)

        error = None
        if category not in FEEDBACK_CATEGORIES:
            error = "Please choose a category."
        elif not TITLE_MIN <= len(title) <= TITLE_MAX:
            error = f"Title must be {TITLE_MIN} to {TITLE_MAX} characters."
        elif not DESC_MIN <= len(description) <= DESC_MAX:
            error = f"Description must be {DESC_MIN} to {DESC_MAX} characters."
        elif rating is None or not 1 <= rating <= 5:
            error = "Please give a rating from 1 to 5."

        if error:
            flash(error, "danger")
        else:
            item = Feedback(user_id=g.user.id, category=category, title=title,
                            description=description, rating=rating,
                            department=g.user.department,  # taken from profile, not typed again
                            is_anonymous=bool(request.form.get("anonymous")))
            db.session.add(item)
            db.session.commit()
            return redirect(url_for("feedback.success", feedback_id=item.id))  # redirect stops double submit

    return render_template("feedback_form.html", categories=FEEDBACK_CATEGORIES, form=request.form)


@feedback_bp.route("/<int:feedback_id>/success")
@login_required
def success(feedback_id):
    item = db.get_or_404(Feedback, feedback_id)
    if item.user_id != g.user.id:
        abort(404)
    return render_template("feedback_success.html", item=item)


@feedback_bp.route("/mine")
@login_required
def my_submissions():
    category = pick(request.args.get("category"), FEEDBACK_CATEGORIES)
    status = pick(request.args.get("status"), STATUSES)
    page = request.args.get("page", 1, type=int)

    query = Feedback.query.filter_by(user_id=g.user.id)
    if category:
        query = query.filter_by(category=category)
    if status:
        query = query.filter_by(status=status)
    pagination = query.order_by(Feedback.created_at.desc(), Feedback.id.desc()).paginate(
        page=page, per_page=PER_PAGE, error_out=False)

    return render_template("my_submissions.html", pagination=pagination, items=pagination.items,
                           category=category, status=status,
                           categories=FEEDBACK_CATEGORIES, statuses=STATUSES)


# ----------------------------------------------------------------- admin side
@feedback_bp.route("/manage")
@admin_required
def manage():
    category = pick(request.args.get("category"), FEEDBACK_CATEGORIES)
    status = pick(request.args.get("status"), STATUSES)
    department = pick(request.args.get("department"), DEPARTMENTS)
    page = request.args.get("page", 1, type=int)

    query = Feedback.query
    if category:
        query = query.filter_by(category=category)
    if status:
        query = query.filter_by(status=status)
    if department:
        query = query.filter_by(department=department)
    pagination = query.order_by(Feedback.created_at.desc(), Feedback.id.desc()).paginate(
        page=page, per_page=PER_PAGE, error_out=False)

    counts = dict(db.session.execute(
        select(Feedback.status, func.count(Feedback.id)).group_by(Feedback.status)).all())

    return render_template("manage_issues.html", pagination=pagination, items=pagination.items,
                           category=category, status=status, department=department, counts=counts,
                           categories=FEEDBACK_CATEGORIES, statuses=STATUSES, departments=DEPARTMENTS)


@feedback_bp.post("/<int:feedback_id>/update")
@admin_required
def update(feedback_id):
    item = db.get_or_404(Feedback, feedback_id)
    status = request.form.get("status")
    note = (request.form.get("admin_note") or "").strip()

    if status not in STATUSES:
        flash("Invalid status.", "danger")
    elif len(note) > NOTE_MAX:
        flash(f"Reply must be {NOTE_MAX} characters or fewer.", "danger")
    else:
        item.status = status
        item.admin_note = note or None
        db.session.commit()
        flash(f"Feedback #{item.id} updated.", "success")

    # Return to the same filters and page the admin was on
    return redirect(url_for(
        "feedback.manage",
        category=pick(request.form.get("category_filter"), FEEDBACK_CATEGORIES),
        status=pick(request.form.get("status_filter"), STATUSES),
        department=pick(request.form.get("department_filter"), DEPARTMENTS),
        page=request.form.get("page", 1, type=int),
        _anchor=f"item-{item.id}"))