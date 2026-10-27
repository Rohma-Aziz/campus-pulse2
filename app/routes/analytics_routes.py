from flask import Blueprint, render_template
from app.analytics import process_analytics, generate_insights, get_chart_data
import pandas as pd

analytics_bp = Blueprint('analytics', __name__, template_folder='../templates')

@analytics_bp.route('/analytics')
def analytics_dashboard():
    # Load data (using your sample csv for now)
    df = pd.read_csv('sample_feedback.csv')
    
    metrics = process_analytics(df)
    insights = generate_insights(df)
    chart_data = get_chart_data(df)
    
    return render_template(
        'analytics.html', 
        metrics=metrics, 
        insights=insights,
        chart_data=chart_data
    )