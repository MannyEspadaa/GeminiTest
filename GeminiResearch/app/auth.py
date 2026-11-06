import functools
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash
from app.db import get_db

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        db = get_db()
        error = None

        if not full_name:
            error = 'Full name is required.'
        elif not username:
            error = 'Username is required.'
        elif not email:
            error = 'Email is required.'
        elif not password:
            error = 'Password is required.'
        else:
            allowed = False
            for dom in current_app_allowed_domains():
                if email.endswith(dom):
                    allowed = True
                    break
            if not allowed:
                error = 'Must use an official university .edu email address.'

        if error is None:
            try:
                hashed_pw = generate_password_hash(password)
                cursor = db.execute(
                    'INSERT INTO users (full_name, username, email, password, verification_token) VALUES (?, ?, ?, ?, ?)',
                    (full_name, username, email, hashed_pw, 'TOKEN-12345')
                )
                db.commit()
            except db.IntegrityError:
                error = f"User {username} or email {email} is already registered."
            else:
                flash('Registration successful! Please verify your email.', 'success')
                return redirect(url_for('auth.verify', email=email))

        flash(error, 'danger')

    return render_template('auth/register.html')

def current_app_allowed_domains():
    return ['.edu', 'university.edu', 'test.edu']

@bp.route('/verify', methods=('GET', 'POST'))
def verify():
    email = request.args.get('email') or request.form.get('email')
    db = get_db()
    if request.method == 'POST':
        token = request.form.get('token')
        user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if user and token == 'TOKEN-12345':
            db.execute('UPDATE users SET is_verified = 1 WHERE email = ?', (email,))
            db.commit()
            flash('Email verified successfully! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Invalid verification token.', 'danger')
    return render_template('auth/verify.html', email=email)

@bp.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        error = None
        user = db.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, username)).fetchone()

        if user is None:
            error = 'Incorrect username or email.'
        elif not check_password_hash(user['password'], password):
            error = 'Incorrect password.'
        elif user['status'] == 'suspended':
            error = 'Your account has been suspended.'
        elif user['status'] == 'removed':
            error = 'Your account has been removed.'
        elif not user['is_verified']:
            error = 'Please verify your email before logging in.'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('main.dashboard'))

        flash(error, 'danger')

    return render_template('auth/login.html')

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        db = get_db()
        g.user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if g.user and g.user['status'] in ('suspended', 'removed'):
            session.clear()
            g.user = None

@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.landing'))

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        return view(**kwargs)
    return wrapped_view

def admin_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None or not g.user['is_admin']:
            flash('Administrator access required.', 'danger')
            return redirect(url_for('main.dashboard'))
        return view(**kwargs)
    return wrapped_view

def game_manager_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None or (not g.user['is_game_manager'] and not g.user['is_admin']):
            flash('Game Manager or Administrator access required.', 'danger')
            return redirect(url_for('main.dashboard'))
        return view(**kwargs)
    return wrapped_view
