import os
import pandas as pd

def process_analytics(csv_path_or_df='sample_feedback.csv'):
    if isinstance(csv_path_or_df, str):
        if os.path.exists(csv_path_or_df):
            df = pd.read_csv(csv_path_or_df)
        else:
            df = pd.DataFrame({
                'department': ['AIDS', 'CS', 'IT', 'EC', 'ME'],
                'category': ['Wi-Fi', 'Canteen', 'Library', 'Hostel', 'Lab'],
                'rating': [3.1, 3.5, 3.7, 3.8, 4.2],
                'status': ['Pending', 'Resolved', 'Resolved', 'Pending', 'Resolved']
            })
    else:
        df = csv_path_or_df

    overall_satisfaction = round(df['rating'].mean(), 2)
    dept_satisfaction = df.groupby('department')['rating'].mean().round(2).to_dict()
    facility_satisfaction = df.groupby('category')['rating'].mean().round(2).to_dict()
    common_issues = df['category'].value_counts().to_dict()
    
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
    resolved_pct = round((df['status'] == 'Resolved').mean() * 100, 1) if 'status' in df.columns else 0.0
    insights.append(f"📊 {resolved_pct}% of total submitted issues have been resolved.")
    return insights

def get_chart_data(df):
    dept_scores = df.groupby('department')['rating'].mean().round(2)
    cat_scores = df.groupby('category')['rating'].mean().round(2)

    return {
        'departments': list(dept_scores.index),
        'dept_ratings': list(dept_scores.values),
        'facilities': list(cat_scores.index),
        'facility_ratings': list(cat_scores.values)
    }

def process_analytics_data():
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

    # metrics aur chart_data dono ki keys yahan properly set hain
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