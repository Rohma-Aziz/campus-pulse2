from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for
from sqlalchemy import select

from app import db
from app.models import CATEGORIES, REPORT_REASONS, Comment, Like, Post, Report
from app.utils import login_required
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
    """Return to the same page/filter. Only validated values go into the URL."""
    category = clean_category(request.form.get("category_filter"))
    page = request.form.get("page", 1, type=int)
    return redirect(url_for("feed.view_feed", category=category, page=page,
                            _anchor=f"post-{post_id}" if post_id else None))


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
        post = Post(user_id=g.user.id, category=category, content=content,
                    is_anonymous=bool(request.form.get("anonymous")))
        db.session.add(post)
        db.session.commit()
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
    # **unpacking use karne se 'metrics', 'insights', aur 'chart_data' direct mil jayenge
    return render_template('analytics.html', **analytics_data)