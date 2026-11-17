from sqlalchemy import text
from app import create_app, db

app = create_app()

TABLES = [
    "faculty_feedback_ratings",
    "faculty_feedback_comments",
    "faculty_feedback_responses",
    "faculty_feedback_questions",
    "faculty_feedback_subjects",
    "faculty_feedback_forms",
]

with app.app_context():
    with db.engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for t in TABLES:
            conn.execute(text(f"DROP TABLE IF EXISTS {t}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    db.create_all()
    print("Faculty feedback tables recreated.")