import sys
from app import create_app, db
from app.models import (User, Post, Comment, Like, Report, CommentReport,
                        Feedback, FacultyFeedbackResponse, FacultyFeedbackForm)

if len(sys.argv) < 2:
    sys.exit("Usage: python delete_user.py user@email.com")

email = sys.argv[1].strip().lower()
app = create_app()

with app.app_context():
    u = User.query.filter_by(email=email).first()
    if not u:
        sys.exit("No user with that email.")

    print(f"User: {u.name} | {u.email} | role={u.role} | dept={u.department}")
    if input("Type DELETE to confirm: ") != "DELETE":
        sys.exit("Cancelled.")

    # forms created by this admin must be handed to another admin first
    forms = FacultyFeedbackForm.query.filter_by(created_by=u.id).all()
    if forms:
        other = input(f"This user created {len(forms)} faculty form(s). "
                      "Email of another admin to take them over: ").strip().lower()
        new_owner = User.query.filter_by(email=other, role="admin").first()
        if not new_owner or new_owner.id == u.id:
            sys.exit("Not a valid different admin. Nothing was deleted.")
        for f in forms:
            f.created_by = new_owner.id
        db.session.flush()

    for post in Post.query.filter_by(user_id=u.id).all():
        db.session.delete(post)            # also removes its comments, likes, reports
    db.session.flush()
    for model in (Comment, Like, Report, CommentReport, Feedback):
        for row in model.query.filter_by(user_id=u.id).all():
            db.session.delete(row)
    for r in FacultyFeedbackResponse.query.filter_by(user_id=u.id).all():
        db.session.delete(r)               # also removes its ratings and comments
    db.session.flush()

    db.session.expire(u)
    db.session.delete(u)
    db.session.commit()
    print("Deleted:", email)