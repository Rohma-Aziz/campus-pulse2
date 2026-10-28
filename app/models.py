from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from app import db

CATEGORIES = ["Academics", "Hostel", "Wi-Fi", "Canteen", "Library", "Events", "Notices", "General"]
DEPARTMENTS = ["CSE", "AIDS", "ECE", "EE", "ME", "Civil", "Other"]
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
    department = db.Column(db.String(50))
    year = db.Column(db.Integer)
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
    department = db.Column(db.String(50), index=True)              # copied from the user's profile
    is_anonymous = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default="Pending", index=True)
    admin_note = db.Column(db.Text)                                # admin's reply to the student
    created_at = db.Column(db.DateTime, default=utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    user = db.relationship("User", backref="feedback_items")