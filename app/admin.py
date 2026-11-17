from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy import func, or_
from functools import wraps
from app.models import Feedback, User, Post, Report, db

admin_bp = Blueprint('admin', __name__, url_prefix='/admin', template_folder='templates')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for('auth.login'))
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            flash("Access denied. Admin privileges required.", "danger")
            return redirect(url_for('feedback.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    return render_template('admin_dashboard.html')

@admin_bp.route('/manage-issues', methods=['GET'])
@admin_required
def manage_issues():
    status_filter = request.args.get('status', '')
    category_filter = request.args.get('category', '')
    dept_filter = request.args.get('department', '')

    query = Feedback.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    if category_filter:
        query = query.filter_by(category=category_filter)
    if dept_filter:
        query = query.filter_by(department=dept_filter)

    items = query.order_by(Feedback.created_at.desc()).all()

    statuses = ['Pending', 'In Progress', 'Resolved']
    counts = {s: Feedback.query.filter_by(status=s).count() for s in statuses}
    
    categories = [c[0] for c in db.session.query(Feedback.category.distinct()).all() if c[0]]
    departments = [d[0] for d in db.session.query(Feedback.department.distinct()).all() if d[0]]

    return render_template(
        'manage_issues.html',
        items=items,
        statuses=statuses,
        counts=counts,
        categories=categories,
        departments=departments,
        status=status_filter,
        category=category_filter,
        department=dept_filter,
        pagination=None  # Safe None pass kiya hai taaki pagination error na aaye
    )

@admin_bp.route('/update-issue/<int:feedback_id>', methods=['POST'])
@admin_required
def update_issue(feedback_id):
    item = Feedback.query.get_or_404(feedback_id)
    new_status = request.form.get('status')
    admin_note = request.form.get('admin_note')

    if new_status:
        item.status = new_status
    if admin_note is not None:
        item.admin_note = admin_note

    db.session.commit()
    flash(f"Issue CP-{item.id:04d} updated successfully!", "success")
    return redirect(url_for('admin.manage_issues'))





@admin_bp.route('/moderation', methods=['GET'])
@admin_required
def moderation_queue():
    # Get IDs of posts that have been reported
    reported_ids = db.session.query(
        Report.post_id
    ).distinct().all()

    reported_ids = [row[0] for row in reported_ids]

    # Show hidden posts and posts that have been reported
    if reported_ids:
        flagged_items = Post.query.filter(
            or_(
                Post.is_hidden.is_(True),
                Post.id.in_(reported_ids)
            )
        ).order_by(Post.created_at.desc()).all()
    else:
        flagged_items = Post.query.filter_by(
            is_hidden=True
        ).order_by(Post.created_at.desc()).all()

    # Count reports for each post
    report_counts = dict(
        db.session.query(
            Report.post_id,
            func.count(Report.id)
        ).group_by(Report.post_id).all()
    )

    return render_template(
        'moderation.html',
        flagged_items=flagged_items,
        report_counts=report_counts
    )


@admin_bp.route('/moderation/approve/<int:item_id>', methods=['POST'])
@admin_required
def approve_content(item_id):
    item = Post.query.get_or_404(item_id)

    # Make the post visible again
    item.is_hidden = False

    # Clear the reports after admin review
    Report.query.filter_by(post_id=item.id).delete(
        synchronize_session=False
    )

    db.session.commit()

    flash("Content approved and made visible.", "success")
    return redirect(url_for('admin.moderation_queue'))



@admin_bp.route('/moderation/remove/<int:item_id>', methods=['POST'])
@admin_required
def remove_content(item_id):
    item = Post.query.get_or_404(item_id)

    # Hide the post from the community feed
    item.is_hidden = True

    # Clear reports after the moderation decision
    Report.query.filter_by(post_id=item.id).delete(
        synchronize_session=False
    )

    db.session.commit()

    flash("Content removed/hidden successfully.", "info")
    return redirect(url_for('admin.moderation_queue'))
