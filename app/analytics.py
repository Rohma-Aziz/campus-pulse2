import os
import pandas as pd
from flask import Blueprint, render_template
from app import db
from app.models import Feedback
from app.utils import login_required

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics', template_folder='templates')

def process_analytics(csv_path_or_df='sample_feedback.csv'):
    feedback_list = Feedback.query.all()
    if feedback_list:
        data = [{
            'department': f.department or 'Other',
            'category': f.category,
            'rating': f.rating,
            'status': f.status
        } for f in feedback_list]
        df = pd.DataFrame(data)
    else:
        if isinstance(csv_path_or_df, str) and os.path.exists(csv_path_or_df):
            df = pd.read_csv(csv_path_or_df)
        else:
            df = pd.DataFrame({
                'department': ['AIDS', 'CS', 'IT', 'EC', 'ME'],
                'category': ['Wi-Fi', 'Canteen', 'Library', 'Hostel', 'Lab'],
                'rating': [3.1, 3.5, 3.7, 3.8, 4.2],
                'status': ['Pending', 'Resolved', 'Resolved', 'Pending', 'Resolved']
            })

    overall_satisfaction = round(df['rating'].mean(), 2) if not df.empty else 0.0
    dept_satisfaction = df.groupby('department')['rating'].mean().round(2).to_dict() if not df.empty else {}
    facility_satisfaction = df.groupby('category')['rating'].mean().round(2).to_dict() if not df.empty else {}
    common_issues = df['category'].value_counts().to_dict() if not df.empty else {}
    
    highest_dept = max(dept_satisfaction, key=dept_satisfaction.get) if dept_satisfaction else "N/A"
    lowest_dept = min(dept_satisfaction, key=dept_satisfaction.get) if dept_satisfaction else "N/A"

    return {
        'overall_satisfaction': overall_satisfaction,
        'dept_satisfaction': dept_satisfaction,
        'facility_satisfaction': facility_satisfaction,
        'common_issues': common_issues,
        'highest_dept': highest_dept,
        'lowest_dept': lowest_dept
    }

def generate_insights(df):
    insights = []
    resolved_pct = round((df['status'] == 'Resolved').mean() * 100, 1) if not df.empty and 'status' in df.columns else 0.0
    insights.append(f"📊 {resolved_pct}% of total submitted issues have been resolved.")
    return insights

def get_chart_data(df):
    if df.empty:
        return {'departments': [], 'dept_ratings': [], 'facilities': [], 'facility_ratings': []}
    dept_scores = df.groupby('department')['rating'].mean().round(2)
    cat_scores = df.groupby('category')['rating'].mean().round(2)
    return {
        'departments': list(dept_scores.index),
        'dept_ratings': list(dept_scores.values),
        'facilities': list(cat_scores.index),
        'facility_ratings': list(cat_scores.values)
    }

def process_analytics_data():
    feedback_list = Feedback.query.all()
    if feedback_list:
        data = [{
            'department': f.department or 'Other',
            'category': f.category,
            'rating': f.rating,
            'status': f.status
        } for f in feedback_list]
        df = pd.DataFrame(data)
    else:
        csv_path = 'sample_feedback.csv'
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
        else:
            df = pd.DataFrame({
                'department': ['AIDS', 'CS', 'IT', 'EC', 'ME'],
                'category': ['Wi-Fi', 'Canteen', 'Library', 'Hostel', 'Lab'],
                'rating': [3.1, 3.5, 3.7, 3.8, 4.2],
                'status': ['Pending', 'Resolved', 'Resolved', 'Pending', 'Resolved']
            })

    summary = process_analytics(df)
    insights = generate_insights(df)
    charts = get_chart_data(df)

    return {
        'metrics': {
            'overall_satisfaction': summary['overall_satisfaction'],
            'highest_dept': summary['highest_dept'],
            'lowest_dept': summary['lowest_dept']
        },
        'insights': insights,
        'chart_data': {
            'dept_labels': charts['departments'],
            'dept_values': charts['dept_ratings'],
            'cat_labels': charts['facilities'],
            'cat_values': charts['facility_ratings']
        }
    }

@analytics_bp.route('/')
@login_required
def analytics_dashboard():
    result = process_analytics_data()
    return render_template(
        'analytics.html',
        metrics=result['metrics'],
        insights=result['insights'],
        chart_data=result['chart_data']
    )