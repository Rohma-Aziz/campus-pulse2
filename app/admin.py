from flask import Blueprint, flash, redirect, render_template, url_for
from sqlalchemy import func, select

from app import db
from app.models import Comment, Post, Report
from app.utils import admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/moderation")
@admin_required
def moderation():
    # Reported posts, most reported first
    reported = db.session.execute(
        select(Post, func.count(Report.id).label("n"))
        .join(Report, Report.post_id == Post.id)
        .where(Post.is_hidden.is_(False))
        .group_by(Post.id)
        .order_by(func.count(Report.id).desc())
    ).all()

    hidden = Post.query.filter_by(is_hidden=True).order_by(Post.created_at.desc()).all()

    # Simple activity numbers per category (a first taste of analytics)
    post_counts = dict(db.session.execute(
        select(Post.category, func.count(Post.id)).where(Post.is_hidden.is_(False)).group_by(Post.category)).all())
    comment_counts = dict(db.session.execute(
        select(Post.category, func.count(Comment.id))
        .join(Comment, Comment.post_id == Post.id).group_by(Post.category)).all())
    stats = sorted(
        [(c, post_counts.get(c, 0), comment_counts.get(c, 0)) for c in set(post_counts) | set(comment_counts)],
        key=lambda row: row[1], reverse=True)

    return render_template("moderation.html", reported=reported, hidden=hidden, stats=stats)


@admin_bp.post("/post/<int:post_id>/hide")
@admin_required
def hide_post(post_id):
    post = db.get_or_404(Post, post_id)
    post.is_hidden = True
    db.session.commit()
    flash("Post hidden from the feed.", "success")
    return redirect(url_for("admin.moderation"))


@admin_bp.post("/post/<int:post_id>/unhide")
@admin_required
def unhide_post(post_id):
    post = db.get_or_404(Post, post_id)
    post.is_hidden = False
    db.session.commit()
    flash("Post restored.", "success")
    return redirect(url_for("admin.moderation"))


@admin_bp.post("/post/<int:post_id>/dismiss")
@admin_required
def dismiss_reports(post_id):
    post = db.get_or_404(Post, post_id)
    for report in list(post.reports):
        db.session.delete(report)
    db.session.commit()
    flash("Reports dismissed.", "success")
    return redirect(url_for("admin.moderation"))


@admin_bp.post("/post/<int:post_id>/delete")
@admin_required
def delete_post(post_id):
    post = db.get_or_404(Post, post_id)
    db.session.delete(post)
    db.session.commit()
    flash("Post deleted.", "info")
    return redirect(url_for("admin.moderation"))