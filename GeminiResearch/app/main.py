from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from app.auth import login_required
from app.db import get_db

bp = Blueprint('main', __name__)

@bp.route('/')
def landing():
    db = get_db()
    public_events = db.execute(
        "SELECT e.*, g.name as game_name FROM events e LEFT JOIN games g ON e.game_id = g.id WHERE e.visibility = 'public' ORDER BY e.date ASC, e.start_time ASC"
    ).fetchall()
    
    public_schedules = db.execute(
        "SELECT s.*, g.name as game_name FROM schedules s JOIN games g ON s.game_id = g.id WHERE s.visibility = 'public' ORDER BY s.date ASC, s.start_time ASC"
    ).fetchall()
    
    games = db.execute('SELECT * FROM games').fetchall()
    return render_template('main/landing.html', events=public_events, schedules=public_schedules, games=games)

@bp.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    rosters = db.execute(
        "SELECT r.*, g.name as game_name FROM roster_members r JOIN games g ON r.game_id = g.id WHERE r.user_id = ?",
        (g.user['id'],)
    ).fetchall()
    
    teams = db.execute(
        "SELECT tm.*, t.name as team_name, g.name as game_name FROM team_members tm JOIN teams t ON tm.team_id = t.id JOIN games g ON t.game_id = g.id WHERE tm.user_id = ?",
        (g.user['id'],)
    ).fetchall()
    
    user_game_ids = [r['game_id'] for r in rosters]
    user_team_ids = [t['team_id'] for t in teams]
    
    games = db.execute('SELECT * FROM games').fetchall()
    events = db.execute(
        "SELECT e.*, g.name as game_name FROM events e LEFT JOIN games g ON e.game_id = g.id WHERE e.visibility = 'public' ORDER BY e.date ASC"
    ).fetchall()
    
    return render_template('main/dashboard.html', rosters=rosters, teams=teams, events=events, games=games)

@bp.route('/profile')
@login_required
def profile():
    db = get_db()
    rosters = db.execute(
        "SELECT r.*, g.name as game_name FROM roster_members r JOIN games g ON r.game_id = g.id WHERE r.user_id = ?",
        (g.user['id'],)
    ).fetchall()
    
    teams = db.execute(
        "SELECT t.name as team_name, g.name as game_name FROM team_members tm JOIN teams t ON tm.team_id = t.id JOIN games g ON t.game_id = g.id WHERE tm.user_id = ?",
        (g.user['id'],)
    ).fetchall()

    return render_template('main/profile.html', profile_user=g.user, rosters=rosters, teams=teams, is_self=True)

@bp.route('/profile/<int:user_id>')
@login_required
def view_user_profile(user_id):
    db = get_db()
    target_user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not target_user:
        flash('User not found.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    rosters = db.execute(
        "SELECT r.*, g.name as game_name FROM roster_members r JOIN games g ON r.game_id = g.id WHERE r.user_id = ?",
        (target_user['id'],)
    ).fetchall()
    
    teams = db.execute(
        "SELECT t.name as team_name, g.name as game_name FROM team_members tm JOIN teams t ON tm.team_id = t.id JOIN games g ON t.game_id = g.id WHERE tm.user_id = ?",
        (target_user['id'],)
    ).fetchall()

    return render_template('main/profile.html', profile_user=target_user, rosters=rosters, teams=teams, is_self=(target_user['id'] == g.user['id']))

@bp.route('/discord/connect', methods=('GET', 'POST'))
@login_required
def discord_connect():
    if request.method == 'POST':
        discord_name = request.form.get('discord_username')
        action = request.form.get('action')
        db = get_db()
        if action == 'fail':
            flash('Discord authentication failed or was rejected.', 'danger')
        elif discord_name:
            db.execute('UPDATE users SET discord_username = ? WHERE id = ?', (discord_name, g.user['id']))
            db.commit()
            flash('Discord account successfully linked!', 'success')
            return redirect(url_for('main.profile'))
        else:
            flash('Please enter a valid Discord username.', 'warning')
    return render_template('main/discord_connect.html')
