from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_mail import Mail, Message
import sqlite3
import os
import secrets
from datetime import timedelta

app = Flask(__name__, template_folder='templates/src/')
app.secret_key = 'super_secret_key_for_session_management'
app.permanent_session_lifetime = timedelta(days=36500)

# --- הגדרות אימייל ---
# Read mail configuration from environment variables for security and flexibility
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', 'noreplyapp289@gmail.com')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', 'ozhcibfpojlgnzvl')

mail = Mail(app)

DB_NAME = "users.db"

def init_db():
    if not os.path.exists(DB_NAME):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()

init_db()

# --- ניהול מצב משחק בזיכרון ---

# שומר מה כל שחקן אמור לראות (הזמנה או תפקיד)
# Mapped by username -> { type: 'invite'/'imposter'/'citizen', content: '...', sender: 'host', id: 'random' }
active_game_states = {}

# שומר את סטטוס השחקנים בלובי עבור המנחה (מי אישר ומי לא)
# Mapped by host_username -> { player_username: 'joined' }
lobby_status = {}

@app.route('/')
def home():
    user = session.get('username')
    return render_template('unified_game.html', user=user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        password = data.get('password')
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        conn.close()
        if result and result[0] == password:
            session['username'] = username
            session.permanent = True
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'שם משתמש או סיסמה שגויים'})
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        password = data.get('password')
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            conn.close()
            session['username'] = username
            session.permanent = True
            return jsonify({'success': True})
        except sqlite3.IntegrityError:
            return jsonify({'success': False, 'message': 'שם המשתמש כבר קיים'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/app-game')
def app_game():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('app_game.html', user=session.get('username'))

# --- לוגיקת משחק ומיילים ---

@app.route('/send_roles', methods=['POST'])
def send_roles():
    data = request.json
    players = data.get('players', [])
    game_type = data.get('gameType')

    try:
        with mail.connect() as conn:
            for p in players:
                if not p.get('email'):
                    continue
                
                content = p.get('wordData', '')
                role = p.get('role')
                name = p.get('name')

                role_header = ""
                if game_type not in ['wordNword', 'categoryNcategory']:
                    role_text = "אימפוסטר" if role == 'imposter' else "אזרח תמים"
                    role_header = f'<h2 style="color: #333;">התפקיד שלך: {role_text}</h2>'

                msg = Message(subject="Imposter Game - המידע שלך למשחק",
                              sender=app.config['MAIL_USERNAME'],
                              recipients=[p['email']])
                
                msg.html = f"""
                <div dir="rtl" style="font-family: Arial, sans-serif; text-align: center; background-color: #f9f9f9; padding: 20px;">
                    <div style="background-color: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                        <h1 style="color: #333;">שלום {name}</h1>
                        {role_header}
                        <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                        <div style="font-size: 24px; font-weight: bold; color: #333; white-space: pre-line;">
                            {content}
                        </div>
                        <p style="color: #888; margin-top: 30px; font-size: 14px;">בהצלחה!</p>
                    </div>
                </div>
                """
                conn.send(msg)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# --- API לאפליקציה ---

@app.route('/api/send_game_data', methods=['POST'])
def send_game_data():
    """ שליחת תפקידים או הזמנות מהמנחה לשחקנים """
    if 'username' not in session:
        return jsonify({'success': False, 'message': 'לא מחובר'}), 401
    
    data = request.json
    players_data = data.get('playersData', [])
    host_user = session['username']
    
    # אתחול הלובי של המנחה אם הוא שולח הזמנות
    if host_user not in lobby_status:
        lobby_status[host_user] = {}

    for player in players_data:
        target_user = player.get('username')
        content = player.get('content')
        msg_type = player.get('type', 'text') # invite, imposter, citizen

        # בדיקה האם השחקן כבר במשחק אחר (רק עבור הזמנות)
        if msg_type == 'invite':
            if target_user in active_game_states:
                # אם יש לו דאטה והוא לא במשחק של המנחה הנוכחי
                existing_data = active_game_states[target_user]
                if existing_data.get('sender') != host_user:
                     return jsonify({'success': False, 'message': f'השחקן {target_user} כבר נמצא במשחק פעיל אחר'})

        active_game_states[target_user] = {
            'content': content,
            'type': msg_type,
            'sender': host_user,
            'id': secrets.token_hex(4)
        }
    
    return jsonify({'success': True})

@app.route('/api/get_my_data')
def get_my_data():
    """ השחקן בודק מה קיבל """
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'}), 401
        
    user = session['username']
    data = active_game_states.get(user)
    
    if data:
        return jsonify({'hasData': True, 'data': data})
    else:
        return jsonify({'hasData': False})

@app.route('/api/update_player_status', methods=['POST'])
def update_player_status():
    """ השחקן מאשר הזמנה או יוצא """
    if 'username' not in session:
        return jsonify({'success': False}), 401
    
    user = session['username']
    data = request.json
    status = data.get('status') # 'joined', 'left'
    host_name = data.get('host')

    if host_name:
        if host_name not in lobby_status:
            lobby_status[host_name] = {}
        
        if status == 'joined':
            lobby_status[host_name][user] = 'joined'
        elif status == 'left':
            lobby_status[host_name].pop(user, None)
            # מחיקת המידע של השחקן (ביטול ההזמנה)
            if user in active_game_states:
                del active_game_states[user]

    return jsonify({'success': True})

@app.route('/api/check_lobby', methods=['GET'])
def check_lobby():
    """ המנחה בודק מי אישר """
    if 'username' not in session:
        return jsonify({'success': False}), 401
        
    host_user = session['username']
    # מחזיר את רשימת השחקנים שאישרו בלובי של המנחה
    approved_players = list(lobby_status.get(host_user, {}).keys())
    
    return jsonify({'success': True, 'approved_players': approved_players})

@app.route('/api/clear_game_data', methods=['POST'])
def clear_game_data():
    if 'username' not in session:
        return jsonify({'success': False}), 401
        
    host_user = session['username']
    
    # ניקוי המידע שנשלח לשחקנים
    users_to_clear = [user for user, data in active_game_states.items() if data.get('sender') == host_user]
    for user in users_to_clear:
        active_game_states.pop(user, None)
    
    # ניקוי הלובי
    if host_user in lobby_status:
        lobby_status[host_user] = {}
        
    return jsonify({'success': True, 'cleared_count': len(users_to_clear)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)