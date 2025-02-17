from flask import Flask, render_template, request, redirect, url_for, abort, session, flash
from flask_mysqldb import MySQL
import MySQLdb.cursors
import hashlib
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import uuid
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Required for session management

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'polls_db'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

# AES Encryption Key (Must be 32 bytes for AES-256)
AES_KEY = b'StrongAES256SecretKey32Bytes!!@#'  # Exactly 32 bytes

# AES Encryption Function
def encrypt_password(plain_text):
    cipher = AES.new(AES_KEY, AES.MODE_CBC)
    encrypted_bytes = cipher.encrypt(pad(plain_text.encode(), AES.block_size))
    return base64.b64encode(cipher.iv + encrypted_bytes).decode()

# AES Decryption Function
def decrypt_password(encrypted_text):
    encrypted_data = base64.b64decode(encrypted_text)
    iv = encrypted_data[:AES.block_size]
    cipher = AES.new(AES_KEY, AES.MODE_CBC, iv)
    decrypted_bytes = unpad(cipher.decrypt(encrypted_data[AES.block_size:]), AES.block_size)
    return decrypted_bytes.decode()

# Initialize database tables (Run once)
def init_db():
    with app.app_context():  # Ensures we are inside the Flask app context
        cursor = mysql.connection.cursor()

        # Create `admin` table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        """)
        
        # Create `polls` table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS polls (
                id INT AUTO_INCREMENT PRIMARY KEY,
                uuid VARCHAR(36) UNIQUE NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT NOT NULL
            )
        """)

         # Create `questions` table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                poll_uuid VARCHAR(36),
                question_text TEXT NOT NULL,
                FOREIGN KEY (poll_uuid) REFERENCES polls(uuid) ON DELETE CASCADE
            )
        """)

        # Create `options` table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS options (
                id INT AUTO_INCREMENT PRIMARY KEY,
                question_id INT,
                option_text TEXT NOT NULL,
                votes INT DEFAULT 0,
                FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
            )
        """)

        # Create `votes` table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS votes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                poll_uuid VARCHAR(36) NOT NULL,
                question_id INT NOT NULL,
                option_id INT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (poll_uuid) REFERENCES polls(uuid) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
                FOREIGN KEY (option_id) REFERENCES options(id) ON DELETE CASCADE
            );
        """)

        # Insert admin only if not exists
        cursor.execute("SELECT * FROM admin WHERE username = 'admin'")
        existing_admin = cursor.fetchone()

        if not existing_admin:
            #Change admin password here, this password for security only
            encrypted_password = encrypt_password("P@ssw0rd1")  # Hardcoded password
            cursor.execute("""
                INSERT INTO admin (username, email, password) 
                VALUES (%s, %s, %s)
            """, ("admin", "admin@gmail.com", encrypted_password))
        
        mysql.connection.commit()
        cursor.close()

@app.route('/')
def index():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM polls")
    polls = cursor.fetchall()
    return render_template('index.html', polls=polls)

@app.route('/create_poll', methods=['GET', 'POST'])
def create_poll():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        poll_uuid = str(uuid.uuid4())  # Generate unique UUID

        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO polls (uuid, title, description) VALUES (%s, %s, %s)", (poll_uuid, title, description))
        mysql.connection.commit()
        poll_id = cursor.lastrowid

        # Insert questions & options
        index = 0
        while True:
            question_text = request.form.get(f'questions[{index}][question]')
            if not question_text:
                break
            cursor.execute("INSERT INTO questions (poll_uuid, question_text) VALUES (%s, %s)", (poll_uuid, question_text))
            question_id = cursor.lastrowid

            options = request.form.getlist(f'questions[{index}][options][]')
            for option in options:
                if option.strip():
                    cursor.execute("INSERT INTO options (question_id, option_text) VALUES (%s, %s)", (question_id, option))

            index += 1
        mysql.connection.commit()
        return redirect(url_for('index'))

    return render_template('create_poll.html')

@app.route('/edit_poll/<string:poll_uuid>', methods=['GET', 'POST'])
def edit_poll(poll_uuid):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM polls WHERE uuid = %s", (poll_uuid,))
    poll = cursor.fetchone()

    if not poll:
        abort(404)

    cursor.execute("SELECT * FROM questions WHERE poll_uuid = %s", (poll_uuid,))
    questions = cursor.fetchall()

    # Ensure options are fetched correctly for each question
    for question in questions:
        cursor.execute("SELECT * FROM options WHERE question_id = %s", (question['id'],))
        question['options'] = cursor.fetchall()

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')

        cursor.execute("UPDATE polls SET title = %s, description = %s WHERE uuid = %s", (title, description, poll_uuid))

        # Remove old questions & options
        cursor.execute("DELETE FROM questions WHERE poll_uuid = %s", (poll_uuid,))
        cursor.execute("DELETE FROM options WHERE question_id NOT IN (SELECT id FROM questions)")

        index = 0
        while True:
            question_text = request.form.get(f'questions[{index}][question]')
            if not question_text:
                break
            cursor.execute("INSERT INTO questions (poll_uuid, question_text) VALUES (%s, %s)", (poll_uuid, question_text))
            question_id = cursor.lastrowid

            options = request.form.getlist(f'questions[{index}][options][]')
            for option in options:
                if option.strip():
                    cursor.execute("INSERT INTO options (question_id, option_text) VALUES (%s, %s)", (question_id, option))
            index += 1

        mysql.connection.commit()
        return redirect(url_for('index'))

    return render_template('edit_poll.html', poll=poll, questions=questions)

@app.route('/delete_poll/<string:poll_uuid>', methods=['POST'])
def delete_poll(poll_uuid):
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM polls WHERE uuid = %s", (poll_uuid,))
    mysql.connection.commit()
    return redirect(url_for('index'))

@app.route('/poll/<string:poll_uuid>', methods=['GET', 'POST'])
def view_poll(poll_uuid):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM polls WHERE uuid = %s", (poll_uuid,))
    poll = cursor.fetchone()

    if not poll:
        abort(404)

    cursor.execute("SELECT * FROM questions WHERE poll_uuid = %s", (poll["uuid"],))
    questions = cursor.fetchall()

    for question in questions:
        cursor.execute("SELECT * FROM options WHERE question_id = %s", (question['id'],))
        question['options'] = cursor.fetchall()

    if request.method == 'POST':
        one_hour_ago = datetime.now() - timedelta(hours=1)

        # Check total votes in the last hour
        cursor.execute("""
            SELECT COUNT(*) FROM votes 
            WHERE timestamp >= %s
        """, (one_hour_ago,))
        
        total_votes = cursor.fetchone()['COUNT(*)']

        if total_votes >= 75:
            flash("The total voting limit of 75 votes per hour has been reached. Try again later!", "danger")
            return redirect(url_for('view_poll', poll_uuid=poll_uuid))

        # Process the vote if limit is not exceeded
        for question in questions:
            selected_option_id = request.form.get(f'question{question["id"]}')
            if selected_option_id:
                cursor.execute("""
                    INSERT INTO votes (poll_uuid, question_id, option_id) 
                    VALUES (%s, %s, %s)
                """, (poll["uuid"], question["id"], selected_option_id))

        mysql.connection.commit()
        cursor.close()

        flash("Your vote has been successfully submitted!", "success")
        return redirect(url_for('poll_results', poll_uuid=poll_uuid))

    return render_template('poll_vote.html', poll=poll, questions=questions)

@app.route('/poll/<string:poll_uuid>/results')
def poll_results(poll_uuid):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM polls WHERE uuid = %s", (poll_uuid,))
    poll = cursor.fetchone()

    if not poll:
        abort(404)

    cursor.execute("SELECT * FROM questions WHERE poll_uuid = %s", (poll["uuid"],))
    questions = cursor.fetchall()

    for question in questions:
        cursor.execute("""
            SELECT options.id, options.option_text, COUNT(votes.id) AS vote_count 
            FROM options 
            LEFT JOIN votes ON options.id = votes.option_id 
            WHERE options.question_id = %s 
            GROUP BY options.id
        """, (question["id"],))
        question['options'] = cursor.fetchall()

    return render_template('poll_results.html', poll=poll, questions=questions)

@app.route('/admin_login', methods=['POST'])
def admin_login():
    username = request.form.get('username')
    password = request.form.get('password')

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM admin WHERE username = %s", (username,))
    admin = cursor.fetchone()

    if admin and decrypt_password(admin['password']) == password:
        session['admin'] = username
        return redirect(url_for('index'))
    else:
        flash("Invalid Credentials", "danger")
        return redirect(url_for('index'))
    
@app.route('/change_password', methods=['POST'])
def change_password():
    if not session.get('admin'):
        abort(403)  # Forbidden if not logged in

    old_password = request.form.get('old_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM admin WHERE username = 'admin'")
    admin = cursor.fetchone()

    # Check if old password is correct
    if not admin or decrypt_password(admin['password']) != old_password:
        session['change_password_error'] = "Incorrect old password!"
        return redirect(url_for('index'))

    # Check if new password matches confirmation
    if new_password != confirm_password:
        session['change_password_error'] = "New password and confirmation do not match!"
        return redirect(url_for('index'))

    # Encrypt new password and update database
    encrypted_new_password = encrypt_password(new_password)
    cursor.execute("UPDATE admin SET password = %s WHERE username = 'admin'", (encrypted_new_password,))
    mysql.connection.commit()
    cursor.close()

    flash("Password successfully changed!", "success")

    # Remove error flag after successful change
    session.pop('change_password_error', None)

    return redirect(url_for('index'))

@app.route('/admin_logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()  # Run once to initialize the database
    app.run(host="0.0.0.0", port=5000, debug=True)
