from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from app.auth import login_required, game_manager_required, admin_required
from app.db import get_db

bp = Blueprint('calendar_bp', __name__)

@bp.route('/events', methods=('GET', 'POST'))
@login_required
def manage_events():
    db = get_db()
    if request.method == 'POST':
        if not g.user['is_game_manager'] and not g.user['is_admin']:
            flash('Unauthorized.', 'danger')
            return redirect(url_for('calendar_bp.manage_events'))
            
        action = request.form.get('action')
        if action == 'create':
            name = request.form.get('name')
            date = request.form.get('date')
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            location = request.form.get('location')
            visibility = request.form.get('visibility', 'public')
            game_id = request.form.get('game_id') or None
            
            if not name or not date or not start_time or not end_time or not location:
                flash('All event fields are required.', 'danger')
            else:
                db.execute(
                    'INSERT INTO events (name, date, start_time, end_time, location, visibility, game_id, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    (name, date, start_time, end_time, location, visibility, game_id, g.user['id'])
                )
                db.commit()
                flash('Event created successfully.', 'success')
        elif action == 'delete':
            event_id = request.form.get('event_id')
            db.execute('DELETE FROM events WHERE id = ?', (event_id,))
            db.commit()
            flash('Event deleted.', 'warning')
            
        return redirect(url_for('calendar_bp.manage_events'))

    events = db.execute('SELECT e.*, g.name as game_name FROM events e LEFT JOIN games g ON e.game_id = g.id ORDER BY e.date ASC').fetchall()
    games = db.execute('SELECT * FROM games').fetchall()
    return render_template('calendar/events.html', events=events, games=games)

@bp.route('/schedules', methods=('GET', 'POST'))
@login_required
def manage_schedules():
    db = get_db()
    if request.method == 'POST':
        if not g.user['is_game_manager'] and not g.user['is_admin']:
            flash('Unauthorized.', 'danger')
            return redirect(url_for('calendar_bp.manage_schedules'))
            
        action = request.form.get('action')
        if action == 'create':
            game_id = request.form.get('game_id')
            title = request.form.get('title')
            date = request.form.get('date')
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            opponent = request.form.get('opponent')
            location = request.form.get('location')
            visibility = request.form.get('visibility', 'roster')
            
            if not g.user['is_admin'] and int(game_id) != g.user['assigned_game_id']:
                flash('You can only create schedules for your assigned game.', 'danger')
                return redirect(url_for('calendar_bp.manage_schedules'))

            conflict = db.execute(
                "SELECT * FROM schedules WHERE game_id = ? AND date = ? AND ((start_time <= ? AND end_time > ?) OR (start_time < ? AND end_time >= ?))",
                (game_id, date, start_time, start_time, end_time, end_time)
            ).fetchone()
            
            if conflict:
                flash('Schedule conflict detected! Another match/event overlaps this time slot.', 'warning')
            else:
                db.execute(
                    'INSERT INTO schedules (game_id, title, date, start_time, end_time, opponent, location, visibility) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    (game_id, title, date, start_time, end_time, opponent, location, visibility)
                )
                db.commit()
                flash('Game schedule created successfully (External calendar sync: SUCCESS).', 'success')
        elif action == 'delete':
            sched_id = request.form.get('sched_id')
            db.execute('DELETE FROM schedules WHERE id = ?', (sched_id,))
            db.commit()
            flash('Schedule deleted.', 'warning')
            
        return redirect(url_for('calendar_bp.manage_schedules'))

    schedules = db.execute('SELECT s.*, g.name as game_name FROM schedules s JOIN games g ON s.game_id = g.id ORDER BY s.date ASC').fetchall()
    games = db.execute('SELECT * FROM games').fetchall()
    return render_template('calendar/schedules.html', schedules=schedules, games=games)
