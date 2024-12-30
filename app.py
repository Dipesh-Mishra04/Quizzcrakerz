from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import openai
import os
import random
import requests

# Load configurations
app = Flask(__name__)
app.config.from_pyfile('config.py')
app.secret_key = os.urandom(24)  # For session management
openai.api_key = app.config['OPENAI_API_KEY']

# Set up MongoDB
client = MongoClient(app.config['MONGO_URI'])
db = client['quizzcrakerz']
users_collection = db['users']
subjects_collection = db['subjects']
questions_collection = db['questions']

# Fetching questions using Open Trivia DB API
def fetch_questions(subject):
    # Example category codes for Open Trivia DB:
    categories = {
        'Computer Networks': 18,
        'Data Structures': 18,
        'Database Management Systems': 18,
        'Web Development': 18,
        'Programming Languages': 18,
        'Operating Systems': 18,
        'Software Engineering': 18,
        'Mathematics for Computing': 19,
        'OOP': 18,
        'Computer Graphics': 18
    }
    category_id = categories.get(subject, 18)

    # API call to Open Trivia DB to fetch questions for the category
    url = f"https://opentdb.com/api.php?amount=10&category={category_id}&type=multiple"
    response = requests.get(url)
    data = response.json()
    
    if data['response_code'] == 0:
        questions = []
        for q in data['results']:
            questions.append({
                'question': q['question'],
                'options': q['incorrect_answers'] + [q['correct_answer']],
                'correct': q['correct_answer']
            })
        random.shuffle(questions)  # Shuffle the options for randomness
        return questions
    else:
        return []

# Helper function to check if user is logged in
def is_logged_in():
    return 'user_id' in session

# Route for Sign Up and Login Page
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        action = request.form['action']  # Check if user is logging in or signing up
        email = request.form['email']
        password = request.form['password']

        if action == 'login':
            # Handle login
            user = users_collection.find_one({'email': email})
            if user and check_password_hash(user['password'], password):
                # Store user session
                session['user_id'] = str(user['_id'])  # Convert ObjectId to string
                return redirect(url_for('dashboard'))
            else:
                # Redirect to the login page with an error
                return render_template('index.html', error="Invalid email or password.")

        elif action == 'signup':
            # Handle signup
            existing_user = users_collection.find_one({'email': email})
            if existing_user:
                return render_template('index.html', error="Email already exists. Please choose a different one.")
            else:
                # Hash the password and save the user to MongoDB
                hashed_password = generate_password_hash(password)
                users_collection.insert_one({'email': email, 'password': hashed_password})
                return redirect(url_for('index'))  # Redirect to login after signup

    return render_template('index.html')

# Route to Dashboard
@app.route('/dashboard')
def dashboard():
    if not is_logged_in():
        return redirect(url_for('index'))  # Redirect to login if not logged in
    
    subjects = list(subjects_collection.find())

    # Convert ObjectId to string for all subjects
    for subject in subjects:
        subject['_id'] = str(subject['_id'])  # Convert ObjectId to string if needed
    
    return render_template('dashboard.html', subjects=subjects)

# Route to logout
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

# Route to Subject Selection (Number of Questions & Time Limit)
@app.route('/subject_selection/<subject_name>', methods=['GET', 'POST'])
def subject_selection(subject_name):
    if request.method == 'POST':
        num_questions = int(request.form['num_questions'])
        time_limit = int(request.form['time_limit'])
        return redirect(url_for('take_test', subject=subject_name, num_questions=num_questions, time_limit=time_limit))
    return render_template('subject_selection.html', subject_name=subject_name)

# Route to start the quiz for a subject
@app.route('/start_quiz/<subject>')
def start_quiz(subject):
    if not is_logged_in():
        return redirect(url_for('index'))  # Redirect to the login page if not logged in

    # Get questions dynamically from API
    questions = fetch_questions(subject)

    if not questions:
        return "Sorry, no questions available at the moment."

    # Set time limit based on the subject
    time_limit = 2 # Set time limit for the subject in minutes (can vary per subject)
    session['time_limit'] = time_limit * 60
    session['subject'] = subject
    session['questions'] = questions

    return render_template('quiz.html', subject=subject, questions=questions, time_limit=time_limit)

# Route to submit the quiz results
@app.route('/submit_quiz', methods=['POST'])
def submit_quiz():
    print(request.form)  # Debug submitted data
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    answers = request.form
    correct_answers = 0
    questions = session.get('questions', [])
    
    # Evaluate score
     # Evaluate score
    for idx, question in enumerate(questions, start=1):  # Use index to match form data
        submitted_answer = answers.get(f"question_{question['question'].replace(' ', '_')}")
        if submitted_answer == question['correct']:
            correct_answers += 1
    # Calculate rank
    total_questions = len(questions)
    rank = f"Your rank is {correct_answers}/{total_questions}"

    # Render results
    return render_template('result.html', score=correct_answers, total=total_questions, rank=rank)

if __name__ == '__main__':
    app.run(debug=True)
