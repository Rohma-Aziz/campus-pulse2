import os


class Config:
    # Set a real secret in your environment:  export SECRET_KEY="long-random-string"
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

    # SQLite by default. For MySQL set:
    #   DATABASE_URL="mysql+pymysql://user:password@localhost/campuspulse"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///campus_pulse.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    POSTS_PER_PAGE = 10

    # Categories only admins can post in (students can still read and comment).
    # Use an empty set() if you want students to post notices too.
    ADMIN_ONLY_CATEGORIES = {"Notices"}