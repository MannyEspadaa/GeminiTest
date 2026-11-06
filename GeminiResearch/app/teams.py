from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from app.auth import login_required, game_manager_required, admin_required
from app.db import get_db

bp = Blueprint('teams', __name__)

@bp.route('/rosters/join/<int:game_id>', methods=('POST',))
@login_required
def join_roster(game_id):
    db = get_db()
    try:
        db.execute('INSERT INTO roster_members (user_id, game_id) VALUES (?, ?)', (g.user['id'], game_id))
        db.commit()
        flash('Successfully joined game roster!', 'success')
    except db.IntegrityError:
        flash('You are already on this roster.', 'info')
    return redirect(url_for('main.dashboard'))

@bp.route('/rosters/leave/<int:game_id>', methods=('POST',))
@login_required
def leave_roster(game_id):
    db = get_db()
    db.execute('DELETE FROM roster_members WHERE user_id = ? AND game_id = ?', (g.user['id'], game_id))
    db.commit()
    flash('Successfully left game roster.', 'success')
    return redirect(url_for('main.dashboard'))

@bp.route('/games/<int:game_id>/teams', methods=('GET', 'POST'))
@login_required
def manage_teams(game_id):
    db = get_db()
    game = db.execute('SELECT * FROM games WHERE id = ?', (game_id,)).fetchone()
    
    if not g.user['is_admin'] and not (g.user['is_game_manager'] and g.user['assigned_game_id'] == game_id):
        flash('Unauthorized access to team management for this game.', 'danger')
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            team_name = request.form.get('team_name')
            if team_name:
                db.execute('INSERT INTO teams (name, game_id) VALUES (?, ?)', (team_name, game_id))
                db.commit()
                flash('Team created successfully.', 'success')
        elif action == 'delete':
            team_id = request.form.get('team_id')
            db.execute('DELETE FROM teams WHERE id = ? AND game_id = ?', (team_id, game_id))
            db.commit()
            flash('Team deleted.', 'warning')
        elif action == 'add_player':
            team_id = request.form.get('team_id')
            user_id = request.form.get('user_id')
            try:
                db.execute('INSERT INTO team_members (user_id, team_id) VALUES (?, ?)', (user_id, team_id))
                db.commit()
                flash('Player promoted and added to team successfully.', 'success')
            except db.IntegrityError:
                flash('User is already on this team.', 'info')
        elif action == 'remove_player':
            team_id = request.form.get('team_id')
            user_id = request.form.get('user_id')
            db.execute('DELETE FROM team_members WHERE user_id = ? AND team_id = ?', (user_id, team_id))
            db.commit()
            flash('Player removed from team.', 'info')
            
        return redirect(url_for('teams.manage_teams', game_id=game_id))

    teams = db.execute('SELECT * FROM teams WHERE game_id = ?', (game_id,)).fetchall()
    roster_users = db.execute(
        "SELECT u.* FROM users u JOIN roster_members rm ON u.id = rm.user_id WHERE rm.game_id = ?",
        (game_id,)
    ).fetchall()
    
    team_members_map = {}
    for t in teams:
        members = db.execute(
            "SELECT u.* FROM users u JOIN team_members tm ON u.id = tm.user_id WHERE tm.team_id = ?",
            (t['id'],)
        ).fetchall()
        team_members_map[t['id']] = members

    return render_template('teams/manage.html', game=game, teams=teams, roster_users=roster_users, team_members_map=team_members_map)
