from flask import Blueprint, render_template, redirect, url_for, flash, g
from app.models import Feedback
import pandas as pd

analytics_bp = Blueprint('analytics', __name__, template_folder='../templates')

@analytics_bp.route('/analytics')
def analytics_dashboard():
    if not g.get('user'):
        flash("Please log in to view analytics.", "warning")
        return redirect(url_for("auth.login"))

    # Fetch real feedback records from the database
    feedback_list = Feedback.query.all()

    if not feedback_list:
        metrics = {
            'overall_satisfaction': 'N/A',
            'highest_dept': 'N/A',
            'lowest_dept': 'N/A'
        }
        insights = ["📊 Not enough data yet to generate insights."]
        chart_data = {
            'dept_labels': [],
            'dept_values': [],
            'cat_labels': [],
            'cat_values': []
        }
        return render_template('analytics.html', metrics=metrics, insights=insights, chart_data=chart_data)

    # Convert database records to Pandas DataFrame for smooth metrics calculation
    data = [{
        'department': f.department or 'Other',
        'category': f.category,
        'rating': f.rating,
        'status': f.status
    } for f in feedback_list]
    
    df = pd.DataFrame(data)

    # Calculations
    overall_satisfaction = round(df['rating'].mean(), 2)
    dept_satisfaction = df.groupby('department')['rating'].mean().round(2).to_dict()
    
    highest_dept = max(dept_satisfaction, key=dept_satisfaction.get) if dept_satisfaction else "N/A"
    lowest_dept = min(dept_satisfaction, key=dept_satisfaction.get) if dept_satisfaction else "N/A"

    metrics = {
        'overall_satisfaction': overall_satisfaction,
        'highest_dept': highest_dept,
        'lowest_dept': lowest_dept
    }

    resolved_pct = round((df['status'] == 'Resolved').mean() * 100, 1) if 'status' in df.columns else 0.0
    insights = [f"📊 {resolved_pct}% of total submitted issues have been resolved."]

    dept_scores = df.groupby('department')['rating'].mean().round(2)
    cat_scores = df.groupby('category')['rating'].mean().round(2)

    chart_data = {
        'dept_labels': list(dept_scores.index),
        'dept_values': list(dept_scores.values),
        'cat_labels': list(cat_scores.index),
        'cat_values': list(cat_scores.values)
    }

    return render_template(
        'analytics.html', 
        metrics=metrics, 
        insights=insights,
        chart_data=chart_data
    )