import csv
import io
from collections import defaultdict

from flask import (Blueprint, Response, abort, flash, g, redirect,
                   render_template, request, url_for)
from sqlalchemy import func

from app import db
from app.models import (DEFAULT_FACULTY_QUESTIONS, DEPARTMENTS,
                        FacultyFeedbackComment, FacultyFeedbackForm,
                        FacultyFeedbackQuestion, FacultyFeedbackRating,
                        FacultyFeedbackResponse, FacultyFeedbackSubject, User,
                        utcnow)
from app.utils import admin_required, check_content_locally, login_required

ff_bp = Blueprint("ff", __name__, url_prefix="/faculty-feedback")

MAX_SUBJECTS = 15
MAX_QUESTIONS = 15
QUESTION_MAX = 200
COMMENT_MAX = 500
SEMESTERS = list(range(1, 9))


# ------------------------------------------------------------------ helpers

def is_super_admin(user):
    # admin whose department is not a real department (default "Admin") sees everything
    return user.is_admin and (user.department or "Admin") == "Admin"


def year_of_semester(sem):
    return (sem + 1) // 2


def semesters_of_year(year):
    return (2 * year - 1, 2 * year)


def forms_visible_to_admin(user):
    q = FacultyFeedbackForm.query
    if not is_super_admin(user):
        q = q.filter_by(department=user.department)
    return q


def get_managed_form(form_id):
    form = db.get_or_404(FacultyFeedbackForm, form_id)
    if not is_super_admin(g.user) and form.department != g.user.department:
        abort(404)
    return form


def open_forms_for_student(user):
    """Published forms for this student's department AND exact semester."""
    if user is None or user.is_admin or not user.department or not user.semester:
        return []
    forms = (FacultyFeedbackForm.query
             .filter(FacultyFeedbackForm.department == user.department,
                     FacultyFeedbackForm.semester == user.semester,
                     FacultyFeedbackForm.is_open == True)
             .order_by(FacultyFeedbackForm.created_at.desc()).all())
    if not forms:
        return []
    done = {r.form_id for r in FacultyFeedbackResponse.query.filter_by(user_id=user.id).all()}
    for f in forms:
        f.already_submitted = f.id in done
    return forms

def get_fillable_form(form_id):
    form = db.get_or_404(FacultyFeedbackForm, form_id)
    u = g.user
    if (not form.is_open or form.department != u.department
            or form.semester != u.semester):
        abort(404)
    return form

def csv_safe(value):
    value = str(value)
    return "'" + value if value[:1] in "=+-@" else value


# ---------------------------------------------------------------- admin side

@ff_bp.route("/admin")
@admin_required
def admin_list():
    dept = request.args.get("department") if is_super_admin(g.user) else None
    q = forms_visible_to_admin(g.user)
    if dept in DEPARTMENTS:
        q = q.filter_by(department=dept)
    forms = q.order_by(FacultyFeedbackForm.created_at.desc()).all()

    counts = dict(db.session.query(FacultyFeedbackResponse.form_id, func.count(FacultyFeedbackResponse.id))
                  .group_by(FacultyFeedbackResponse.form_id).all())
    return render_template("ff_admin_list.html", forms=forms, counts=counts,
                           super_admin=is_super_admin(g.user), dept=dept)


@ff_bp.route("/admin/new", methods=["GET", "POST"])
@admin_required
def admin_new():
    super_admin = is_super_admin(g.user)

    if request.method == "POST":
        department = request.form.get("department") if super_admin else g.user.department
        semester = request.form.get("semester", type=int)
        session_label = (request.form.get("session_label") or "").strip()
        title = (request.form.get("title") or "").strip()

        faculty = [x.strip() for x in request.form.getlist("faculty")]
        subject = [x.strip() for x in request.form.getlist("subject")]
        pairs = [(f, s) for f, s in zip(faculty, subject) if f and s]

        questions = []
        for i in request.form.getlist("default_q", type=int):
            if 0 <= i < len(DEFAULT_FACULTY_QUESTIONS):
                questions.append(DEFAULT_FACULTY_QUESTIONS[i])
        for line in (request.form.get("custom_questions") or "").splitlines():
            line = line.strip()
            if line and line.lower() not in [q.lower() for q in questions]:
                questions.append(line)

        error = None
        if department not in DEPARTMENTS:
            error = "Please choose a department."
        elif semester not in SEMESTERS:
            error = "Please choose a semester (1 to 8)."
        elif not session_label or len(session_label) > 20:
            error = "Enter the academic session, e.g. 2026-27."
        elif not pairs:
            error = "Add at least one faculty and subject."
        elif len(pairs) > MAX_SUBJECTS:
            error = f"A form can have at most {MAX_SUBJECTS} faculty/subject rows."
        elif any(len(f) > 100 or len(s) > 120 for f, s in pairs):
            error = "Faculty or subject name is too long."
        elif not questions:
            error = "Select or add at least one question."
        elif len(questions) > MAX_QUESTIONS:
            error = f"A form can have at most {MAX_QUESTIONS} questions."
        elif any(len(q) > QUESTION_MAX for q in questions):
            error = f"Each question must be {QUESTION_MAX} characters or fewer."
        elif FacultyFeedbackForm.query.filter_by(department=department, semester=semester,
                                                 session_label=session_label).first():
            error = (f"A form for {department}, semester {semester} ({session_label}) already exists. "
                     "Close or delete it first.")

        if error:
            flash(error, "danger")
        else:
            form = FacultyFeedbackForm(
                department=department, semester=semester, session_label=session_label,
                title=title[:150] or f"Faculty Feedback - {department} - Semester {semester} ({session_label})",
                created_by=g.user.id, is_open=False)
            form.questions = [FacultyFeedbackQuestion(text=t, position=i) for i, t in enumerate(questions)]
            form.subjects = [FacultyFeedbackSubject(faculty_name=f, subject_name=s, position=i)
                             for i, (f, s) in enumerate(pairs)]
            db.session.add(form)
            db.session.commit()
            flash("Form generated. Students cannot see it until you publish it.", "success")
            return redirect(url_for("ff.admin_list"))

    return render_template("ff_admin_new.html", super_admin=super_admin, departments=DEPARTMENTS,
                           semesters=SEMESTERS, default_questions=DEFAULT_FACULTY_QUESTIONS,
                           form=request.form)


@ff_bp.post("/admin/<int:form_id>/toggle")
@admin_required
def admin_toggle(form_id):
    form = get_managed_form(form_id)
    if form.is_open:
        form.is_open = False
        form.closed_at = utcnow()
        flash("Form closed. Students can no longer see or submit it.", "info")
    else:
        form.is_open = True
        form.opened_at = utcnow()
        form.closed_at = None
        flash(f"Form published. {form.department} students of semester {form.semester} "
              "will now see it in Submit Feedback.", "success")
    db.session.commit()
    return redirect(url_for("ff.admin_list"))


@ff_bp.post("/admin/<int:form_id>/delete")
@admin_required
def admin_delete(form_id):
    form = get_managed_form(form_id)
    resp_ids = [r.id for r in form.responses]
    if resp_ids:
        FacultyFeedbackRating.query.filter(FacultyFeedbackRating.response_id.in_(resp_ids)).delete(synchronize_session=False)
        FacultyFeedbackComment.query.filter(FacultyFeedbackComment.response_id.in_(resp_ids)).delete(synchronize_session=False)
        FacultyFeedbackResponse.query.filter(FacultyFeedbackResponse.id.in_(resp_ids)).delete(synchronize_session=False)
    db.session.expire_all()
    db.session.delete(db.session.get(FacultyFeedbackForm, form_id))
    db.session.commit()
    flash("Form and its responses deleted.", "info")
    return redirect(url_for("ff.admin_list"))


@ff_bp.route("/admin/<int:form_id>/analytics")
@admin_required
def admin_analytics(form_id):
    form = get_managed_form(form_id)
    data = compute_analytics(form)
    return render_template("ff_analytics.html", form=form, a=data)


@ff_bp.route("/admin/<int:form_id>/export.csv")
@admin_required
def admin_export(form_id):
    form = get_managed_form(form_id)
    a = compute_analytics(form)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([form.title])
    w.writerow(["Responses", a["n_responses"]])
    w.writerow([])
    w.writerow(["Faculty", "Subject", "Overall"] + a["question_labels"])
    for s in a["subjects"]:
        w.writerow([csv_safe(s["faculty"]), csv_safe(s["subject"]), s["avg"] if s["avg"] is not None else ""]
                   + [v if v is not None else "" for v in s["by_question"]])
    w.writerow([])
    w.writerow(["All faculty", "", a["overall"] if a["overall"] is not None else ""]
               + [v if v is not None else "" for v in a["question_avgs"]])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=faculty_feedback_{form.id}.csv"})


# -------------------------------------------------------------- student side

@ff_bp.route("/form/<int:form_id>", methods=["GET", "POST"])
@login_required
def fill(form_id):
    if g.user.is_admin:
        flash("Admins generate forms; students fill them.", "info")
        return redirect(url_for("ff.admin_list"))

    form = get_fillable_form(form_id)
    if FacultyFeedbackResponse.query.filter_by(form_id=form.id, user_id=g.user.id).first():
        flash("You have already submitted this form. Thank you!", "info")
        return redirect(url_for("feedback.submit"))

    if request.method == "POST":
        ratings, comments, error = [], [], None
        for s in form.subjects:
            for q in form.questions:
                val = request.form.get(f"r_{s.id}_{q.id}", type=int)
                if val is None or not 1 <= val <= 5:
                    error = f"Please rate every question for {s.faculty_name} ({s.subject_name})."
                    break
                ratings.append((s.id, q.id, val))
            if error:
                break
            text = (request.form.get(f"c_{s.id}") or "").strip()
            if text:
                if len(text) > COMMENT_MAX:
                    error = f"Comments must be {COMMENT_MAX} characters or fewer."
                    break
                flagged, reason = check_content_locally(text)
                if flagged:
                    error = f"Your comment for {s.faculty_name} was blocked. {reason}"
                    break
                comments.append((s.id, text))

        if error:
            flash(error, "danger")
        else:
            resp = FacultyFeedbackResponse(form_id=form.id, user_id=g.user.id)
            resp.ratings = [FacultyFeedbackRating(subject_id=sid, question_id=qid, rating=v)
                            for sid, qid, v in ratings]
            resp.comments = [FacultyFeedbackComment(subject_id=sid, text=t) for sid, t in comments]
            db.session.add(resp)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                flash("You have already submitted this form.", "info")
                return redirect(url_for("feedback.submit"))
            flash("Faculty feedback submitted anonymously. Thank you!", "success")
            return redirect(url_for("feedback.submit"))

    return render_template("ff_fill.html", form=form, posted=request.form)


# ----------------------------------------------------------------- analytics

def _avg(values):
    return round(sum(values) / len(values), 2) if values else None


def compute_analytics(form):
    questions = list(form.questions)
    subjects = list(form.subjects)
    qpos = {q.id: i for i, q in enumerate(questions)}
    spos = {s.id: i for i, s in enumerate(subjects)}

    rows = (db.session.query(FacultyFeedbackRating.subject_id, FacultyFeedbackRating.question_id,
                             FacultyFeedbackRating.rating)
            .join(FacultyFeedbackResponse, FacultyFeedbackRating.response_id == FacultyFeedbackResponse.id)
            .filter(FacultyFeedbackResponse.form_id == form.id).all())
    n_responses = FacultyFeedbackResponse.query.filter_by(form_id=form.id).count()

    cell = defaultdict(list)
    by_q = defaultdict(list)
    by_s = defaultdict(list)
    dist = {i: 0 for i in range(1, 6)}
    all_ratings = []
    for sid, qid, r in rows:
        if sid in spos and qid in qpos:
            cell[(sid, qid)].append(r)
            by_q[qid].append(r)
            by_s[sid].append(r)
            dist[r] = dist.get(r, 0) + 1
            all_ratings.append(r)

    question_labels = [q.text for q in questions]
    question_avgs = [_avg(by_q[q.id]) for q in questions]
    subject_rows = []
    for s in subjects:
        subject_rows.append({
            "id": s.id, "faculty": s.faculty_name, "subject": s.subject_name,
            "avg": _avg(by_s[s.id]),
            "by_question": [_avg(cell[(s.id, q.id)]) for q in questions],
        })
    overall = _avg(all_ratings)

    comments = defaultdict(list)
    for c in (FacultyFeedbackComment.query
              .join(FacultyFeedbackResponse, FacultyFeedbackComment.response_id == FacultyFeedbackResponse.id)
              .filter(FacultyFeedbackResponse.form_id == form.id)
              .order_by(FacultyFeedbackComment.id.desc()).all()):
        comments[c.subject_id].append(c.text)
    for s in subject_rows:
        s["comments"] = comments.get(s["id"], [])

    eligible = User.query.filter_by(role="student", department=form.department,
                                    year=year_of_semester(form.semester)).count()

    total_ratings = len(all_ratings)
    pct_high = round(100 * (dist[4] + dist[5]) / total_ratings, 1) if total_ratings else None
    pct_low = round(100 * (dist[1] + dist[2]) / total_ratings, 1) if total_ratings else None

    prev = previous_form_stats(form)
    insights = build_insights(form, n_responses, eligible, overall, question_labels, question_avgs,
                              subject_rows, pct_high, pct_low, prev)

    return {
        "n_responses": n_responses, "eligible": eligible,
        "response_rate": round(100 * n_responses / eligible, 1) if eligible else None,
        "overall": overall, "pct_high": pct_high, "pct_low": pct_low,
        "question_labels": question_labels, "question_avgs": question_avgs,
        "subjects": subject_rows,
        "faculty_labels": [f"{s['faculty']} ({s['subject']})" for s in subject_rows],
        "faculty_avgs": [s["avg"] for s in subject_rows],
        "distribution": [dist[i] for i in range(1, 6)],
        "prev": prev, "insights": insights,
    }


def previous_form_stats(form):
    older = (FacultyFeedbackForm.query
             .filter(FacultyFeedbackForm.department == form.department,
                     FacultyFeedbackForm.id != form.id,
                     FacultyFeedbackForm.created_at < form.created_at)
             .order_by(FacultyFeedbackForm.created_at.desc()).all())
    for f in older:
        avg = (db.session.query(func.avg(FacultyFeedbackRating.rating))
               .join(FacultyFeedbackResponse, FacultyFeedbackRating.response_id == FacultyFeedbackResponse.id)
               .filter(FacultyFeedbackResponse.form_id == f.id).scalar())
        if avg is not None:
            return {"title": f"Semester {f.semester} ({f.session_label})", "avg": round(float(avg), 2)}
    return None


def build_insights(form, n, eligible, overall, q_labels, q_avgs, subjects, pct_high, pct_low, prev):
    if n == 0 or overall is None:
        return ["No student has submitted this form yet."]

    out = []

    if n < 5:
        out.append(f"Only {n} response(s) so far. Treat these numbers as indicative, not final.")
    if eligible:
        rate = 100 * n / eligible
        if rate < 30:
            out.append(f"Low participation: {n} of {eligible} registered students ({rate:.0f}%) have responded. "
                       "Consider reminding students before closing the form.")
        else:
            out.append(f"{n} of {eligible} registered students ({rate:.0f}%) have responded.")

    verdict = ("excellent" if overall >= 4.5 else "good" if overall >= 4 else
               "average" if overall >= 3 else "poor")
    out.append(f"Overall teaching score is {overall}/5 ({verdict}); {pct_high}% of all ratings are 4 or 5 "
               f"and {pct_low}% are 1 or 2.")

    if prev:
        diff = round(overall - prev["avg"], 2)
        if abs(diff) < 0.05:
            out.append(f"Score is unchanged compared with {prev['title']} ({prev['avg']}/5).")
        else:
            word = "up" if diff > 0 else "down"
            out.append(f"Score is {word} by {abs(diff)} compared with {prev['title']} ({prev['avg']}/5).")

    scored = [(a, l) for a, l in zip(q_avgs, q_labels) if a is not None]
    if len(scored) > 1:
        best, worst = max(scored), min(scored)
        out.append(f"Strongest area: \"{best[1]}\" ({best[0]}/5). "
                   f"Weakest area: \"{worst[1]}\" ({worst[0]}/5).")
    weak_q = [f"\"{l}\" ({a})" for a, l in scored if a < 3.5]
    if weak_q:
        out.append("Parameters scoring below 3.5 that need attention: " + ", ".join(weak_q) + ".")

    ranked = sorted([s for s in subjects if s["avg"] is not None], key=lambda s: s["avg"], reverse=True)
    if len(ranked) > 1:
        top, bottom = ranked[0], ranked[-1]
        out.append(f"Highest rated: {top['faculty']} - {top['subject']} ({top['avg']}/5). "
                   f"Lowest rated: {bottom['faculty']} - {bottom['subject']} ({bottom['avg']}/5).")
        if top["avg"] - bottom["avg"] >= 1.0:
            out.append(f"There is a gap of {round(top['avg'] - bottom['avg'], 2)} points between the highest "
                       "and lowest rated faculty; a review discussion may help.")

    cells = []
    for s in subjects:
        for label, v in zip(q_labels, s["by_question"]):
            if v is not None and v < 3:
                cells.append((v, s["faculty"], s["subject"], label))
    cells.sort()
    for v, fac, sub, label in cells[:3]:
        out.append(f"Needs attention: {fac} ({sub}) scored {v}/5 on \"{label}\".")
    if len(cells) > 3:
        out.append(f"{len(cells) - 3} more faculty/parameter combinations are also below 3/5 (see heatmap).")
    if not cells and not weak_q:
        out.append("No faculty or parameter scored below 3/5 or 3.5/5 respectively.")

    return out

@ff_bp.post("/my-semester")
@login_required
def set_semester():
    if g.user.is_admin:
        flash("Admins do not have a semester.", "danger")
    elif g.user.semester:
        flash("Your semester is locked. Ask your department admin to change it.", "warning")
    else:
        sem = request.form.get("semester", type=int)
        if sem not in SEMESTERS:
            flash("Please choose a valid semester (1 to 8).", "danger")
        else:
            g.user.semester = sem
            g.user.year = year_of_semester(sem)
            db.session.commit()
            flash(f"Semester set to {sem}.", "success")
    return redirect(url_for("feedback.submit"))