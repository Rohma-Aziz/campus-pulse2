from flask import Blueprint, flash, redirect, render_template, url_for
from sqlalchemy import func, select

from app import db
from app.models import Post, Report
from app.utils import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/moderation")
@admin_required
def moderation():
    counts = dict(db.session.execute(
        select(Report.post_id, func.count(Report.id)).group_by(Report.post_id)).all())

    # Auto-hidden posts and posts with reports
    flagged_posts = (Post.query
                     .filter(Post.is_hidden.is_(True) | Post.id.in_(list(counts)))
                     .order_by(Post.created_at.desc()).all())
    for post in flagged_posts:
        post.report_count = counts.get(post.id, 0)

    return render_template("moderation.html", flagged_posts=flagged_posts)


@admin_bp.post("/post/<int:post_id>/approve")
@admin_required
def approve_post(post_id):
    post = db.get_or_404(Post, post_id)
    post.is_hidden = False
    for report in list(post.reports):
        db.session.delete(report)
    db.session.commit()
    flash("Post approved and visible again.", "success")
    return redirect(url_for("admin.moderation"))


@admin_bp.post("/post/<int:post_id>/remove")
@admin_required
def remove_post(post_id):
    post = db.get_or_404(Post, post_id)
    db.session.delete(post)
    db.session.commit()
    flash("Post removed permanently.", "info")
    return redirect(url_for("admin.moderation"))