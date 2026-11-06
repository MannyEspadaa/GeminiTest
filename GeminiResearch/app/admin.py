from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from app.auth import admin_required
from app.db import get_db

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/users')
@admin_required
def user_management():
    db = get_db()
    users = db.execute('SELECT u.*, g.name as game_name FROM users u LEFT JOIN games g ON u.assigned_game_id = g.id').fetchall()
    games = db.execute('SELECT * FROM games').fetchall()
    return render_template('admin/users.html', users=users, games=games)

@bp.route('/users/<int:user_id>/role', methods=('POST',))
@admin_required
def update_role(user_id):
    db = get_db()
    role_type = request.form.get('role_type')
    action = request.form.get('action')
    game_id = request.form.get('game_id')

    if role_type == 'admin':
        is_admin = 1 if action == 'grant' else 0
        db.execute('UPDATE users SET is_admin = ? WHERE id = ?', (is_admin, user_id))
    elif role_type == 'game_manager':
        is_gm = 1 if action == 'grant' else 0
        g_id = game_id if action == 'grant' and game_id else None
        db.execute('UPDATE users SET is_game_manager = ?, assigned_game_id = ? WHERE id = ?', (is_gm, g_id, user_id))
    
    db.commit()
    flash('User roles updated successfully.', 'success')
    return redirect(url_for('admin.user_management'))

@bp.route('/users/<int:user_id>/moderate', methods=('POST',))
@admin_required
def moderate_user(user_id):
    db = get_db()
    action = request.form.get('action')
    
    if action == 'suspend':
        db.execute("UPDATE users SET status = 'suspended' WHERE id = ?", (user_id,))
        flash('User account suspended.', 'warning')
    elif action == 'unsuspend':
        db.execute("UPDATE users SET status = 'active' WHERE id = ?", (user_id,))
        flash('User account unsuspended.', 'success')
    elif action == 'remove':
        db.execute("UPDATE users SET status = 'removed' WHERE id = ?", (user_id,))
        flash('User account removed/deactivated.', 'danger')
        
    db.commit()
    return redirect(url_for('admin.user_management'))
