from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models import Feedback, User, db
from functools import wraps

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
    # Flagged ya reported items fetch karein
    flagged_items = Feedback.query.filter((Feedback.is_flagged == True) | (Feedback.reports > 0) | (Feedback.status == 'Pending')).all()
    return render_template('moderation.html', flagged_items=flagged_items)

@admin_bp.route('/moderation/approve/<int:item_id>', methods=['POST'])
@admin_required
def approve_content(item_id):
    item = Feedback.query.get_or_404(item_id)
    item.is_flagged = False
    item.reports = 0
    item.is_hidden = False
    db.session.commit()
    flash("Content approved and made visible.", "success")
    return redirect(url_for('admin.moderation_queue'))

@admin_bp.route('/moderation/remove/<int:item_id>', methods=['POST'])
@admin_required
def remove_content(item_id):
    item = Feedback.query.get_or_404(item_id)
    item.is_hidden = True
    item.is_flagged = False
    db.session.commit()
    flash("Content removed/hidden successfully.", "info")
    return redirect(url_for('admin.moderation_queue'))