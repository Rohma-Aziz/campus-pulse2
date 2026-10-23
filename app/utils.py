from functools import wraps
from flask import abort, flash, g, redirect, url_for
import os
import requests
from flask import current_app

from better_profanity import profanity

# Load default bad words list
profanity.load_censor_words()

def check_content_locally(text):
    if not text:
        return False, None
    # profanity.contains_profanity returns True if bad words are found
    if profanity.contains_profanity(text):
        return True, "Flagged: Contains restricted or profane language."
    return False, None


# Add your own extra words
profanity.add_censor_words(["sala", "kutta", "pagal", "gadha"])



def moderate(text):
    """Local filter first, then API. Returns (is_flagged, reason)."""
    flagged, reason = check_content_locally(text)
    if flagged:
        return True, reason
    return check_content_locally(text)  

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in first.", "warning")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in first.", "warning")
            return redirect(url_for("auth.login"))
        if not g.user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped