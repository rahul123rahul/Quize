from flask import Flask, request, redirect, session, render_template, jsonify, send_file
from datetime import timedelta, datetime
from database import get_db_connection
from certificate_generator import generate_certificate_pdf
import random
import docx  # pip install python-docx
import os
import requests
import io
import csv

app = Flask(__name__)
app.secret_key = 'super_static_key_do_not_change'

# --- CONFIG ---
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365)
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True

# --- 1. AUTH ROUTES ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM Users WHERE email=%s AND password_hash=%s", (email, password))
            user = cursor.fetchone()
        conn.close()

        if user:
            if user.get('is_blocked', 0) == 1: return "<h1>ACCOUNT BLOCKED</h1>"
            session.permanent = True
            session['user_id'] = user['user_id']
            session['role'] = user['role']
            session['name'] = user['full_name']
            
            if user['role'] == 'Admin': return redirect('/admin')
            elif user['role'] == 'Coordinator': return redirect('/coordinator')
            else: return redirect('/student')
        return "Login Failed"
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    conn = get_db_connection()
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        session_interest = request.form.get('session_interest', 'General')
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM Users WHERE email=%s", (email,))
            if cursor.fetchone(): return "<h1>Email registered!</h1>"
            cursor.execute("INSERT INTO Users (full_name, email, password_hash, role, selected_session) VALUES (%s, %s, %s, 'Student', %s)", 
                           (name, email, password, session_interest))
            conn.commit()
        conn.close()
        return redirect('/') 
    with conn.cursor() as cursor:
        cursor.execute("SELECT DISTINCT category FROM Quizzes")
        rows = cursor.fetchall() or []
        categories = [row['category'] for row in rows]
    conn.close()
    return render_template('register.html', categories=categories)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# --- 2. ADMIN DASHBOARD ---
@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'Admin': return redirect('/')
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Get Quizzes
            cursor.execute("SELECT * FROM Quizzes")
            quizzes = cursor.fetchall() or []

            # Get Questions (Safe Join)
            cursor.execute("""
                SELECT q.*, COALESCE(z.title, 'General') as session_name, COALESCE(q.quiz_id, '0') as quiz_id_safe
                FROM Questions q LEFT JOIN Quizzes z ON q.quiz_id = z.quiz_id ORDER BY q.question_id DESC
            """)
            questions = cursor.fetchall() or []

            # Get Coordinators
            cursor.execute("SELECT * FROM Users WHERE role='Coordinator'")
            coordinators = cursor.fetchall() or []
            
            # Get Results
            cursor.execute("""SELECT a.*, u.full_name, q.title, a.certificate_approved
                              FROM Quiz_Attempts a 
                              JOIN Users u ON a.user_id=u.user_id 
                              JOIN Quizzes q ON a.quiz_id=q.quiz_id 
                              ORDER BY a.total_score DESC""")
            attempts = cursor.fetchall() or []

            # Calculate Winners
            winners = []
            if attempts:
                high_score = max(a['total_score'] for a in attempts)
                winners = [a for a in attempts if a['total_score'] == high_score]

            # Analytics Stats
            total_students = len(set(a['user_id'] for a in attempts))
            total_exams = len(attempts)
            avg_score = round(sum(a['total_score'] for a in attempts) / total_exams, 1) if total_exams > 0 else 0

    except Exception as e:
        print(f"DB Error: {e}")
        quizzes, questions, coordinators, attempts, winners = [], [], [], [], []
        total_students, total_exams, avg_score = 0, 0, 0
    finally:
        conn.close()

    return render_template('admin_dashboard.html', 
                           attempts=attempts, coordinators=coordinators, 
                           questions=questions, quizzes=quizzes, winners=winners,
                           stats={'students': total_students, 'exams': total_exams, 'avg': avg_score})

# --- 3. COORDINATOR DASHBOARD ---
@app.route('/coordinator')
def coordinator_dashboard():
    if session.get('role') != 'Coordinator': return redirect('/')
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM Quizzes")
            quizzes = cursor.fetchall()
            
            # CRITICAL: Fetch Students for the table
            cursor.execute("SELECT * FROM Users WHERE role='Student'")
            students = cursor.fetchall()
            
            cursor.execute("""
                SELECT q.*, COALESCE(z.title, 'General') as session_name, COALESCE(q.quiz_id, '0') as quiz_id_safe 
                FROM Questions q LEFT JOIN Quizzes z ON q.quiz_id = z.quiz_id ORDER BY q.question_id DESC
            """)
            questions = cursor.fetchall()
            
            cursor.execute("""SELECT a.*, u.full_name, q.title, a.certificate_approved
                              FROM Quiz_Attempts a 
                              JOIN Users u ON a.user_id=u.user_id 
                              JOIN Quizzes q ON a.quiz_id=q.quiz_id 
                              ORDER BY a.total_score DESC""")
            attempts = cursor.fetchall()
            
    except Exception as e:
        print(f"Coordinator DB Error: {e}")
        quizzes, questions, students, attempts = [], [], [], []
    finally:
        conn.close()

    return render_template('coordinator_dashboard.html', quizzes=quizzes, questions=questions, students=students, attempts=attempts, name=session['name'])

# --- 4. SESSION MANAGEMENT ---
@app.route('/create_quiz_session', methods=['POST'])
def create_quiz_session():
    if session.get('role') not in ['Admin', 'Coordinator']: return "Denied"
    
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("INSERT INTO Quizzes (title, category, duration_minutes, total_marks, start_time) VALUES (%s, %s, %s, %s, %s)", 
                       (request.form['title'], request.form['category'], request.form['duration'], request.form['total_marks'], request.form['start_time']))
        conn.commit()
    conn.close()
    return redirect(request.referrer)

@app.route('/session/edit/<int:quiz_id>', methods=['POST'])
def edit_session(quiz_id):
    if session.get('role') != 'Admin': return "Denied"
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("""UPDATE Quizzes SET title=%s, category=%s, duration_minutes=%s, total_marks=%s, start_time=%s 
                          WHERE quiz_id=%s""", 
                       (request.form['title'], request.form['category'], request.form['duration'], request.form['total_marks'], request.form['start_time'], quiz_id))
        conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/session/delete/<int:quiz_id>')
def delete_session(quiz_id):
    if session.get('role') != 'Admin': return "Denied"
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM Quizzes WHERE quiz_id=%s", (quiz_id,))
        cursor.execute("DELETE FROM Questions WHERE quiz_id=%s", (quiz_id,))
        conn.commit()
    conn.close()
    return redirect('/admin')

# --- 5. QUESTION MANAGEMENT ---
@app.route('/admin/add_manual_question', methods=['POST'])
def add_manual_question():
    if session.get('role') not in ['Admin', 'Coordinator']: return "Denied"
    
    quiz_id = request.form.get('quiz_id')
    q_text = request.form.get('q_text')
    
    if not quiz_id or not q_text: return "Error: Missing Data"

    conn = get_db_connection()
    with conn.cursor() as cursor:
        if request.form.get('q_type') == 'MCQ':
            cursor.execute("""INSERT INTO Questions (quiz_id, question_type, question_text, option_a, option_b, option_c, option_d, correct_option, marks)
                              VALUES (%s, 'MCQ', %s, %s, %s, %s, %s, %s, %s)""", 
                           (quiz_id, q_text, request.form.get('opt_a'), request.form.get('opt_b'), request.form.get('opt_c'), request.form.get('opt_d'), request.form.get('correct_opt'), request.form.get('marks')))
        else:
            cursor.execute("""INSERT INTO Questions (quiz_id, question_type, question_text, test_input, test_output, marks)
                              VALUES (%s, 'CODE', %s, %s, %s, %s)""", 
                           (quiz_id, q_text, request.form.get('test_input'), request.form.get('test_output'), request.form.get('marks')))
        conn.commit()
    conn.close()
    return redirect(request.referrer)

@app.route('/question/edit/<int:q_id>', methods=['GET', 'POST'])
def edit_question(q_id):
    if session.get('role') not in ['Admin', 'Coordinator']: return "Denied"
    conn = get_db_connection()

    if request.method == 'POST':
        with conn.cursor() as cursor:
            cursor.execute("""UPDATE Questions SET question_text=%s, option_a=%s, option_b=%s, option_c=%s, option_d=%s, correct_option=%s, marks=%s 
                              WHERE question_id=%s""", 
                           (request.form['q_text'], request.form['opt_a'], request.form['opt_b'], request.form['opt_c'], request.form['opt_d'], request.form['correct'], request.form['marks'], q_id))
            conn.commit()
        conn.close()
        return redirect(request.referrer or '/admin')

    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM Questions WHERE question_id=%s", (q_id,))
        q = cursor.fetchone()
    conn.close()
    return render_template('edit_question.html', q=q)

@app.route('/question/delete/<int:q_id>')
def delete_question(q_id):
    if session.get('role') not in ['Admin', 'Coordinator']: return "Denied"
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM Questions WHERE question_id=%s", (q_id,))
        conn.commit()
    conn.close()
    return redirect(request.referrer)

@app.route('/admin/delete_bulk_questions', methods=['POST'])
def delete_bulk_questions():
    if session.get('role') not in ['Admin', 'Coordinator']: return "Denied"
    ids = request.form.getlist('q_ids')
    if not ids: return "No questions selected"
    
    conn = get_db_connection()
    with conn.cursor() as cursor:
        fmt = ','.join(['%s'] * len(ids))
        cursor.execute(f"DELETE FROM Questions WHERE question_id IN ({fmt})", tuple(ids))
        conn.commit()
    conn.close()
    return redirect(request.referrer)

@app.route('/upload_docx', methods=['POST'])
def upload_docx():
    if 'file' not in request.files: return "No file"
    file = request.files['file']
    quiz_id = request.form.get('quiz_id')
    if not quiz_id: return "Error: Select Session"
    
    doc = docx.Document(file)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for table in doc.tables:
        for i, row in enumerate(table.rows):
            if i == 0: continue
            c = [cell.text.strip() for cell in row.cells]
            if len(c) >= 7:
                cursor.execute("INSERT INTO Questions (quiz_id, question_type, question_text, option_a, option_b, option_c, option_d, correct_option, marks) VALUES (%s, 'MCQ', %s, %s, %s, %s, %s, %s, %s)", 
                               (quiz_id, c[0], c[1], c[2], c[3], c[4], c[5], c[6]))
    conn.commit()
    conn.close()
    return redirect(request.referrer)

# --- 6. STUDENT & EXAM ---
@app.route('/student')
def student_dashboard():
    if session.get('role') != 'Student': return redirect('/')
    conn = get_db_connection()
    with conn.cursor() as cursor:
        now = datetime.now()
        cursor.execute("SELECT * FROM Quizzes ORDER BY start_time ASC")
        quizzes = cursor.fetchall()
        
        available = []
        for q in quizzes:
            # Fix Date Format if needed
            if isinstance(q['start_time'], str):
                try: q['start_time'] = datetime.strptime(q['start_time'], '%Y-%m-%d %H:%M:%S')
                except: q['start_time'] = datetime.strptime(q['start_time'].replace('T', ' '), '%Y-%m-%d %H:%M')
            
            if not q['start_time'] or now >= q['start_time']:
                q.update({'is_locked': False, 'time_msg': "Live Now", 'seconds_left': 0})
            else:
                diff = q['start_time'] - now
                q.update({'is_locked': True, 'time_msg': f"Starts: {q['start_time']}", 'seconds_left': int(diff.total_seconds())})
            available.append(q)

        cursor.execute("""SELECT q.title, a.total_score, a.status, a.attempt_id, a.certificate_approved 
                          FROM Quiz_Attempts a JOIN Quizzes q ON a.quiz_id=q.quiz_id WHERE a.user_id=%s""", (session['user_id'],))
        history = cursor.fetchall()
        
        cursor.execute("SELECT * FROM Announcements WHERE id=1")
        ann = cursor.fetchone()
    conn.close()
    msg = ann['message'] if (ann and ann['is_active']) else None
    return render_template('student_dashboard.html', quizzes=available, history=history, name=session['name'], winner_announce=msg)

@app.route('/quiz/<int:quiz_id>')
def quiz_interface(quiz_id):
    if 'user_id' not in session: return redirect('/')
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM Quizzes WHERE quiz_id=%s", (quiz_id,))
        meta = cursor.fetchone()
        
        cursor.execute("SELECT * FROM Questions WHERE quiz_id=%s", (quiz_id,))
        questions = cursor.fetchall()
        random.shuffle(questions)

        cursor.execute("SELECT attempt_id, status FROM Quiz_Attempts WHERE user_id=%s AND quiz_id=%s", (session['user_id'], quiz_id))
        existing = cursor.fetchone()
        
        if existing:
            if existing['status'] != 'In-Progress': return "<h1>Exam Finished</h1><a href='/student'>Return</a>"
            attempt_id = existing['attempt_id']
        else:
            cursor.execute("INSERT INTO Quiz_Attempts (user_id, quiz_id, total_score, status) VALUES (%s, %s, 0, 'In-Progress')", (session['user_id'], quiz_id))
            conn.commit()
            attempt_id = cursor.lastrowid
        
        # Get saved answers
        cursor.execute("SELECT question_id, selected_option, is_flagged FROM Quiz_Responses WHERE attempt_id=%s", (attempt_id,))
        saved = {row['question_id']: {'opt': row['selected_option'], 'flag': row['is_flagged']} for row in cursor.fetchall()}

    conn.close()
    return render_template('exam_console.html', questions=questions, attempt_id=attempt_id, quiz_meta=meta, saved_responses=saved)

@app.route('/api/save_answer', methods=['POST'])
def save_answer():
    data = request.json
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("""INSERT INTO Quiz_Responses (attempt_id, question_id, selected_option, is_flagged) 
                          VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE selected_option=%s, is_flagged=%s""", 
                       (data['attempt_id'], data['question_id'], data['option'], data.get('is_flagged', 0), data['option'], data.get('is_flagged', 0)))
        conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/api/submit_quiz', methods=['POST'])
def submit_quiz():
    aid = request.json['attempt_id']
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) as score FROM Quiz_Responses r JOIN Questions q ON r.question_id=q.question_id WHERE r.attempt_id=%s AND r.selected_option=q.correct_option", (aid,))
        score = cursor.fetchone()['score'] * 5
        cursor.execute("UPDATE Quiz_Attempts SET total_score=%s, status='Completed' WHERE attempt_id=%s", (score, aid))
        conn.commit()
    conn.close()
    return jsonify({'score': score})

@app.route('/api/run_code', methods=['POST'])
def run_code():
    data = request.json
    payload = {"language": "python", "version": "3.10.0", "files": [{"content": data.get('code')}], "stdin": data.get('input')}
    try:
        res = requests.post('https://emkc.org/api/v2/piston/execute', json=payload).json()
        actual = res['run']['stdout'].strip() if 'run' in res else "Error"
        is_correct = (actual == data.get('expected', '').strip())
        
        if is_correct:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("REPLACE INTO Quiz_Responses (attempt_id, question_id, selected_option) VALUES (%s, %s, 'CODE_SUCCESS')", (data['attempt_id'], data['question_id']))
                conn.commit()
            conn.close()
        return jsonify({'status': 'success', 'output': actual, 'is_correct': is_correct})
    except Exception as e: return jsonify({'status': 'error', 'output': str(e)})

# --- 7. ADMIN EXTRAS ---
@app.route('/admin/announce_winner', methods=['POST'])
def announce_winner():
    if session.get('role') != 'Admin': return "Denied"
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("UPDATE Announcements SET message=%s, is_active=1 WHERE id=1", (f"🏆 Top Scorer: {request.form['winner_name']}",))
        conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/admin/clear_announcement')
def clear_announcement():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("UPDATE Announcements SET is_active=0 WHERE id=1")
        conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/admin/approve_cert/<int:attempt_id>')
def approve_cert(attempt_id):
    if session.get('role') != 'Admin': return "Denied"
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("UPDATE Quiz_Attempts SET certificate_approved=1 WHERE attempt_id=%s", (attempt_id,))
        conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/download/cert/<int:attempt_id>')
def download_cert(attempt_id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT u.full_name, q.title, a.total_score, a.status, a.certificate_approved FROM Quiz_Attempts a JOIN Users u ON a.user_id=u.user_id JOIN Quizzes q ON a.quiz_id=q.quiz_id WHERE a.attempt_id=%s", (attempt_id,))
        data = cursor.fetchone()
    conn.close()
    
    if not data or data['status'] != 'Completed': return "Exam not completed."
    if data['certificate_approved'] == 0: return "<h1>Certificate Locked</h1><p>Contact Admin.</p>"

    pdf = generate_certificate_pdf(data['full_name'], data['title'], int(data['total_score']), datetime.now().strftime("%Y-%m-%d"), attempt_id)
    return send_file(pdf, as_attachment=True, download_name=f"Certificate_{data['full_name']}.pdf", mimetype='application/pdf')

@app.route('/admin/delete_user/<int:user_id>')
def delete_user(user_id):
    if session.get('role') != 'Admin': return "Denied"
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM Users WHERE user_id=%s", (user_id,))
        cursor.execute("UPDATE Quiz_Attempts SET user_id=NULL WHERE user_id=%s", (user_id,))
        conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/admin/create_coordinator', methods=['POST'])
def create_coordinator():
    if session.get('role') != 'Admin': return "Denied"
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("INSERT INTO Users (full_name, email, password_hash, role) VALUES (%s, %s, %s, 'Coordinator')", (request.form['name'], request.form['email'], request.form['password']))
        conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/admin/export_results')
def export_results():
    if session.get('role') != 'Admin': return "Denied"
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT a.attempt_id, u.full_name, u.email, q.title, a.total_score, a.status FROM Quiz_Attempts a JOIN Users u ON a.user_id=u.user_id JOIN Quizzes q ON a.quiz_id=q.quiz_id")
        rows = cursor.fetchall()
    conn.close()
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Name', 'Email', 'Quiz', 'Score', 'Status'])
    for r in rows: cw.writerow([r['attempt_id'], r['full_name'], r['email'], r['title'], r['total_score'], r['status']])
    
    resp = send_file(io.BytesIO(si.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name='results.csv')
    return resp

if __name__ == '__main__':
    app.run(debug=True, port=5000)