from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from app import db

CATEGORIES = ["Academics", "Hostel", "Wi-Fi", "Canteen", "Library", "Events", "Notices", "General"]
DEPARTMENTS = [
    "Computer Science & Engineering (CSE)",
    "CSE with Artificial Intelligence & Data Science (AI & DS)",
    "CSE with Artificial Intelligence & Machine Learning (AI & ML)",
    "CSE with Cyber Security",
    "Computer Science & Information Technology (CSIT)",
    "Civil",
    "Mechanical",
    "Electrical",
    "Electrical & Electronics",
    "Electrical & Communication",
]
REPORT_REASONS = ["Spam", "Abusive or offensive", "Off-topic", "Other"]
FEEDBACK_CATEGORIES = [c for c in CATEGORIES if c != "Notices"]
STATUSES = ["Pending", "In Progress", "Resolved"]

def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")  # student | admin
    department = db.Column(db.String(100))
    year = db.Column(db.Integer)
    semester = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=utcnow)

    posts = db.relationship("Post", backref="author", lazy=True)
    comments = db.relationship("Comment", backref="author", lazy=True)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    @property
    def is_admin(self):
        return self.role == "admin"


class Post(db.Model):
    __tablename__ = "posts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category = db.Column(db.String(50), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    is_anonymous = db.Column(db.Boolean, nullable=False, default=False)
    is_hidden = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=utcnow, index=True)

    comments = db.relationship("Comment", backref="post", lazy="selectin",
                               order_by="Comment.created_at", cascade="all, delete-orphan")
    likes = db.relationship("Like", backref="post", lazy="selectin", cascade="all, delete-orphan")
    reports = db.relationship("Report", backref="post", lazy=True, cascade="all, delete-orphan")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    comment_text = db.Column(db.Text, nullable=False)
    is_official = db.Column(db.Boolean, nullable=False, default=False)  # admin response
    created_at = db.Column(db.DateTime, default=utcnow)
    reports = db.relationship("CommentReport", backref="comment",
                              cascade="all, delete-orphan")

    @property
    def is_hidden(self):
        return len(self.reports) >= 3


class Like(db.Model):
    __tablename__ = "likes"
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    __table_args__ = (db.UniqueConstraint("post_id", "user_id", name="uq_like_once"),)


class Report(db.Model):
    __tablename__ = "reports"
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reason = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    __table_args__ = (db.UniqueConstraint("post_id", "user_id", name="uq_report_once"),)

class CommentReport(db.Model):
    __tablename__ = "comment_reports"

    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey("comments.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    __table_args__ = (
        db.UniqueConstraint("comment_id", "user_id", name="uq_comment_report_once"),
    )

class Feedback(db.Model):
    """Structured feedback (rating + status). This is the table the analytics page reads."""
    __tablename__ = "feedback_entries"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=False)                 # 1 to 5
    department = db.Column(db.String(100), index=True)              # copied from the user's profile
    is_anonymous = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default="Pending", index=True)
    admin_note = db.Column(db.Text)                                # admin's reply to the student
    created_at = db.Column(db.DateTime, default=utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    user = db.relationship("User", backref="feedback_items")


# ======================================================================
#  Faculty feedback (semester-wise, department-wise forms)
# ======================================================================

# Questions every auto-generated form starts with. Admin can untick any of
# them or add custom ones when generating a form. All are rated 1 to 5.
DEFAULT_FACULTY_QUESTIONS = [
    "Timely course completion",
    "Doubt solving",
    "Faculty involvement in teaching",
    "Clarity of concepts explained",
    "Punctuality and regularity of classes",
    "Use of examples, practicals and teaching aids",
    "Syllabus coverage and pace of teaching",
    "Approachability and behaviour towards students",
    "Fairness of internal assessment",
    "Overall teaching effectiveness",
]


class FacultyFeedbackForm(db.Model):
    """One form = one department + one semester + one academic session."""
    __tablename__ = "faculty_feedback_forms"
    id = db.Column(db.Integer, primary_key=True)
    department = db.Column(db.String(100), nullable=False, index=True)
    semester = db.Column(db.Integer, nullable=False)                 # 1 to 8
    session_label = db.Column(db.String(20), nullable=False)         # e.g. "2026-27"
    title = db.Column(db.String(150), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    is_open = db.Column(db.Boolean, nullable=False, default=False)   # admin "publishes" the form
    opened_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utcnow)

    questions = db.relationship("FacultyFeedbackQuestion", backref="form", lazy=True,
                                order_by="FacultyFeedbackQuestion.position",
                                cascade="all, delete-orphan")
    subjects = db.relationship("FacultyFeedbackSubject", backref="form", lazy=True,
                               order_by="FacultyFeedbackSubject.position",
                               cascade="all, delete-orphan")
    responses = db.relationship("FacultyFeedbackResponse", backref="form", lazy=True,
                                cascade="all, delete-orphan")
    creator = db.relationship("User", foreign_keys=[created_by])


class FacultyFeedbackQuestion(db.Model):
    __tablename__ = "faculty_feedback_questions"
    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey("faculty_feedback_forms.id"), nullable=False, index=True)
    text = db.Column(db.String(200), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)


class FacultyFeedbackSubject(db.Model):
    """A (faculty, subject) pair the students rate on this form."""
    __tablename__ = "faculty_feedback_subjects"
    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey("faculty_feedback_forms.id"), nullable=False, index=True)
    faculty_name = db.Column(db.String(100), nullable=False)
    subject_name = db.Column(db.String(120), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)


class FacultyFeedbackResponse(db.Model):
    """One student's submission for one form. user_id is only used to stop
    double submission; analytics never shows who said what."""
    __tablename__ = "faculty_feedback_responses"
    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey("faculty_feedback_forms.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    ratings = db.relationship("FacultyFeedbackRating", backref="response", lazy=True,
                              cascade="all, delete-orphan")
    comments = db.relationship("FacultyFeedbackComment", backref="response", lazy=True,
                               cascade="all, delete-orphan")
    __table_args__ = (db.UniqueConstraint("form_id", "user_id", name="uq_faculty_feedback_once"),)


class FacultyFeedbackRating(db.Model):
    __tablename__ = "faculty_feedback_ratings"
    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey("faculty_feedback_responses.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("faculty_feedback_subjects.id"), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey("faculty_feedback_questions.id"), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)  # 1 to 5


class FacultyFeedbackComment(db.Model):
    __tablename__ = "faculty_feedback_comments"
    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey("faculty_feedback_responses.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("faculty_feedback_subjects.id"), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
