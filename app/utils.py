from functools import wraps

from flask import abort, flash, g, redirect, url_for


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