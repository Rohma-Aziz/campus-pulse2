from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import CATEGORIES, REPORT_REASONS, Comment, CommentReport, Like, Post, Report
from app.utils import login_required, moderate
from app.analytics import process_analytics_data


feed_bp = Blueprint("feed", __name__, url_prefix="/feed")

POST_MIN, POST_MAX = 5, 1000
COMMENT_MAX = 500


def postable_categories(user):
    admin_only = current_app.config["ADMIN_ONLY_CATEGORIES"]
    return [c for c in CATEGORIES if user.is_admin or c not in admin_only]


def clean_category(value):
    return value if value in CATEGORIES else None


def back_to_feed(post_id=None):
    """Return to the exact page/filter the user was on."""
    ref = request.referrer
    if ref and ref.startswith(request.host_url):
        return redirect(ref)
    return redirect(url_for("feed.view_feed"))


def visible_post_or_404(post_id):
    post = db.get_or_404(Post, post_id)
    if post.is_hidden and not g.user.is_admin:
        abort(404)
    return post


@feed_bp.route("/")
@login_required
def view_feed():
    category = clean_category(request.args.get("category"))
    page = request.args.get("page", 1, type=int)

    query = Post.query.filter_by(is_hidden=False)
    if category:
        query = query.filter_by(category=category)
    pagination = query.order_by(Post.created_at.desc(), Post.id.desc()).paginate(
        page=page, per_page=current_app.config["POSTS_PER_PAGE"], error_out=False)

    ids = [p.id for p in pagination.items]
    liked, reported = set(), set()
    if ids:
        liked = set(db.session.scalars(
            select(Like.post_id).where(Like.user_id == g.user.id, Like.post_id.in_(ids))))
        reported = set(db.session.scalars(
            select(Report.post_id).where(Report.user_id == g.user.id, Report.post_id.in_(ids))))

    return render_template("feed.html", pagination=pagination, posts=pagination.items,
                           category=category, liked=liked, reported=reported,
                           postable=postable_categories(g.user), report_reasons=REPORT_REASONS,
                           post_max=POST_MAX, comment_max=COMMENT_MAX)


@feed_bp.post("/create")
@login_required
def create_post():
    content = (request.form.get("content") or "").strip()
    category = request.form.get("category")

    if category not in postable_categories(g.user):
        flash("You can't post in that category.", "danger")
    elif not POST_MIN <= len(content) <= POST_MAX:
        flash(f"Posts must be {POST_MIN} to {POST_MAX} characters.", "danger")
    else:
        is_flagged, reason = moderate(content)

        post = Post(
            user_id=g.user.id,
            category=category,
            content=content,
            is_anonymous=bool(request.form.get("anonymous")),
            is_hidden=is_flagged,  # hidden automatically if profanity is found
        )
        db.session.add(post)
        db.session.commit()

        if is_flagged:
            flash("Your post was flagged and hidden for admin review.", "warning")
        else:
            flash("Your post has been shared with the campus!", "success")

    return redirect(url_for("feed.view_feed"))


@feed_bp.post("/post/<int:post_id>/like")
@login_required
def toggle_like(post_id):
    post = visible_post_or_404(post_id)
    existing = Like.query.filter_by(post_id=post.id, user_id=g.user.id).first()
    if existing:
        db.session.delete(existing)
    else:
        db.session.add(Like(post_id=post.id, user_id=g.user.id))
    db.session.commit()
    return back_to_feed(post.id)


@feed_bp.post("/post/<int:post_id>/comment")
@login_required
def add_comment(post_id):
    post = visible_post_or_404(post_id)
    text = (request.form.get("comment_text") or "").strip()
    if not 1 <= len(text) <= COMMENT_MAX:
        flash(f"Comments must be 1 to {COMMENT_MAX} characters.", "danger")
    elif moderate(text)[0]:
        flash("Your comment contains language that isn't allowed.", "warning")
    else:
        db.session.add(Comment(post_id=post.id, user_id=g.user.id, comment_text=text,
                               is_official=g.user.is_admin))
        db.session.commit()
    return back_to_feed(post.id)


@feed_bp.post("/post/<int:post_id>/report")
@login_required
def report_post(post_id):
    post = visible_post_or_404(post_id)
    reason = request.form.get("reason")
    if reason not in REPORT_REASONS:
        flash("Please choose a reason.", "danger")
    elif Report.query.filter_by(post_id=post.id, user_id=g.user.id).first():
        flash("You already reported this post.", "info")
    else:
        db.session.add(Report(post_id=post.id, user_id=g.user.id, reason=reason))
        db.session.commit()

        if Report.query.filter_by(post_id=post.id).count() >= 3:
            post.is_hidden = True
            db.session.commit()
            flash("Thanks. This post was hidden after multiple reports.", "success")
        else:
            flash("Thanks. An admin will review this post.", "success")
    return back_to_feed(post.id)


@feed_bp.post("/post/<int:post_id>/delete")
@login_required
def delete_post(post_id):
    post = db.get_or_404(Post, post_id)
    if post.user_id != g.user.id and not g.user.is_admin:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash("Post deleted.", "info")
    return back_to_feed()


@feed_bp.route('/analytics')
@login_required
def analytics_dashboard():
    analytics_data = process_analytics_data()
    return render_template('analytics.html', **analytics_data)


@feed_bp.post("/comment/delete/<int:comment_id>")
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    post = Post.query.get(comment.post_id)
    if comment.user_id == g.user.id or post.user_id == g.user.id or g.user.is_admin:
        db.session.delete(comment)
        db.session.commit()
        flash("Comment removed successfully.", "success")
    else:
        flash("You do not have permission to delete this comment.", "danger")
        
    return back_to_feed()


@feed_bp.post("/comment/<int:comment_id>/report")
@login_required
def report_comment(comment_id):
    comment = db.get_or_404(Comment, comment_id)

    if comment.user_id == g.user.id:
        flash("You can't report your own comment.", "info")
    elif CommentReport.query.filter_by(comment_id=comment.id, user_id=g.user.id).first():
        flash("You already reported this comment.", "info")
    else:
        db.session.add(CommentReport(comment_id=comment.id, user_id=g.user.id))
        try:
            db.session.commit()
            flash("Thanks. The comment was reported.", "success")
        except IntegrityError:
            db.session.rollback()
            flash("You already reported this comment.", "info")
    return back_to_feed()
