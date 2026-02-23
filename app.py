# ===============================
# IMPORTS
# ===============================
import pickle
import numpy as np
import pandas as pd
import smtplib
import re
import os
import json
import sqlite3
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import uuid

from database import get_connection
from auth_utils import hash_password, verify_password
from resume_parser import extract_text, extract_resume_features, ats_score, ats_grade_resume_analysis
from feature_builder import (
    communication_score,
    coding_questionnaire_score,
    coding_score_from_questionnaire,
    resume_score
)

# ===============================
# CONSTANTS
# ===============================
EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
UPLOAD_DIR = "uploads"
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}
ALLOWED_MARKS_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_marks_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_MARKS_EXTENSIONS

# ===============================
# ENVIRONMENT
# ===============================
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
ALERT_FROM = os.getenv("ALERT_FROM", SMTP_USER)
ALERT_THRESHOLD = float(os.getenv("ALERT_THRESHOLD", 0.5))

# ===============================
# FLASK APP (ONLY ONCE!)
# ===============================
FRONTEND_DIR = BASE_DIR.parent / "frontend"
app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
app.secret_key = os.getenv("SECRET_KEY", os.urandom(24).hex())
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
CORS(app)

os.makedirs(UPLOAD_DIR, exist_ok=True)

# ===============================
# LOAD ML MODEL
# ===============================
try:
    with open(BASE_DIR / "placement_randomforest_bundle.pkl", "rb") as f:
        bundle = pickle.load(f)
    
    model = bundle["model"]
    scaler = bundle["scaler"]
    selector = bundle["selector"]
    
    print("Model loaded successfully")
except Exception as e:
    print(f"Error loading model: {e}")
    model = None
    scaler = None
    selector = None

def calculate_v_score(cgpa, coding_score, comm_score, resume_score, num_projects, num_internships):
    """Centralized v_score calculation - SINGLE SOURCE OF TRUTH"""
    try:
        if model is not None:
            ml_features = {
                "cgpa": cgpa,
                "coding_score": coding_score,
                "communication_score": comm_score,
                "resume_score": resume_score,
                "num_projects": num_projects,
                "number_of_skills": num_projects * 2  # Estimate
            }
            X = create_features_from_input(ml_features)
            X_scaled = scaler.transform(X)
            X_sel = selector.transform(X_scaled)
            v_score = float(model.predict_proba(X_sel)[0, 1]) * 100
        else:
            # Consistent fallback formula
            v_score = (
                cgpa/10 * 35 + 
                coding_score/100 * 25 + 
                comm_score/100 * 15 + 
                resume_score/100 * 15 + 
                min(1, num_projects/3) * 5 + 
                min(1, num_internships) * 5
            )
    except Exception:
        # Consistent fallback formula
        v_score = (
            cgpa/10 * 35 + 
            coding_score/100 * 25 + 
            comm_score/100 * 15 + 
            resume_score/100 * 15 + 
            min(1, num_projects/3) * 5 + 
            min(1, num_internships) * 5
        )
    
    return min(100, max(0, round(v_score, 2)))
def create_features_from_input(d):
    df = pd.DataFrame([d])
    df["cgpa_coding"] = df["cgpa"] * df["coding_score"]
    df["projects_skills"] = df["num_projects"] * df["number_of_skills"]
    df["skills_per_project"] = df["number_of_skills"] / (df["num_projects"] + 1)
    df["avg_score"] = (
        df["cgpa"] + df["coding_score"] +
        df["communication_score"] + df["resume_score"]
    ) / 4
    return df

# ===============================
# EMAIL ALERT
# ===============================
def send_tpo_email(tpo_email, payload, v_score_percent):
    try:
        if not SMTP_USER or not SMTP_PASS:
            print("Email credentials not configured")
            return False
        
        print(f"DEBUG: Attempting to send email to {tpo_email}")
        print(f"DEBUG: SMTP Config - Host: {SMTP_HOST}, Port: {SMTP_PORT}, User: {SMTP_USER}")
            
        msg = MIMEMultipart()
        msg["From"] = ALERT_FROM
        msg["To"] = tpo_email
        msg["Subject"] = "Placement Alert — Student at Risk"

        # v_score_percent is already in 0-100 range from ML model
        body = f"""
Hello TPO,

Student Details:
{payload}

Placement Probability: {v_score_percent:.1f}%

— Placement Prediction System
"""
        msg.attach(MIMEText(body, "plain"))

        print(f"DEBUG: Connecting to SMTP server...")
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
            print(f"DEBUG: Logging in...")
            smtp.login(SMTP_USER, SMTP_PASS)
            print(f"DEBUG: Sending message...")
            smtp.send_message(msg)
            
        print(f"Alert email sent to {tpo_email} for high-risk student")
        return True
        
    except Exception as e:
        print(f"Failed to send email: {e}")
        print(f"Email error details - Type: {type(e).__name__}, Message: {str(e)}")
        return False

# ===============================
# STUDENT REGISTER
# ===============================
@app.route("/api/student/register", methods=["POST"])
def student_register():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON data"}), 400
        
    register_number = data.get("register_number", "").strip().upper()
    password = data.get("password", "").strip()

    if not register_number:
        return jsonify({"error": "Register number is required"}), 400

    if len(password) < 5:
        return jsonify({"error": "Password must be at least 5 characters"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO students_auth (register_number, password_hash) VALUES (?, ?)",
            (register_number, hash_password(password))
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Register number already registered"}), 409
    except Exception:
        return jsonify({"error": "Registration failed"}), 500
    finally:
        conn.close()

    return jsonify({"message": "Successfully registered! You can login now 🎉"}), 201

# -----------------------
# STUDENT LOGIN (DETAILED ERRORS)
# -----------------------
@app.route("/api/student/login", methods=["POST"])
def student_login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON data"}), 400
        
    register_number = data.get("register_number", "").strip().upper()
    password = data.get("password", "").strip()

    if not register_number:
        return jsonify({"error": "Register number is required"}), 400

    conn = get_connection()
    cur = conn.cursor()

    # Check if user exists
    cur.execute(
        "SELECT id, password_hash FROM students_auth WHERE register_number=?",
        (register_number,)
    )
    user = cur.fetchone()
    conn.close()

    if not user:
        return jsonify({"error": "User not registered"}), 404

    if not verify_password(password, user[1]):
        return jsonify({"error": "Incorrect password"}), 401

    # Successful login - store register number in session
    session["user_id"] = user[0]
    session["register_number"] = register_number
    session["role"] = "student"
    return jsonify({"message": "Login successful"}), 200

@app.route("/api/session/check", methods=["GET"])
def check_session():
    """Debug endpoint to check current session"""
    return jsonify({
        "role": session.get("role"),
        "register_number": session.get("register_number"),
        "user_id": session.get("user_id"),
        "tpo_email": session.get("tpo_email"),
        "session_keys": list(session.keys())
    })

@app.route("/api/student/logout", methods=["POST"])
def student_logout():
    """Logout student and clear session"""
    session.clear()
    return jsonify({"message": "Logged out successfully"}), 200

# ===============================
# TPO LOGIN
# ===============================
@app.route("/api/tpo/login", methods=["POST"])
def tpo_login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON data"}), 400
        
    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()

    if not email:
        return jsonify({"error": "Email is required"}), 400

    if not re.match(EMAIL_REGEX, email):
        return jsonify({"error": "Invalid email format"}), 400

    conn = get_connection()
    cur = conn.cursor()

    # Check if TPO exists
    cur.execute(
        "SELECT id, password_hash FROM tpo_auth WHERE email=?",
        (email,)
    )
    tpo = cur.fetchone()
    conn.close()

    if not tpo:
        return jsonify({"error": "TPO not registered"}), 404

    if not verify_password(password, tpo[1]):
        return jsonify({"error": "Incorrect password"}), 401

    # Successful login - store TPO info in session
    session["tpo_id"] = tpo[0]
    session["tpo_email"] = email
    session["role"] = "tpo"
    return jsonify({"message": "Login successful"}), 200

@app.route("/api/tpo/logout", methods=["POST"])
def tpo_logout():
    """Logout TPO and clear session"""
    session.clear()
    return jsonify({"message": "Logged out successfully"}), 200


# ===============================
# STUDENT PROFILE MANAGEMENT
# ===============================

@app.route("/api/student/profile/load", methods=["GET"])
def load_student_profile():
    """Load student profile based on logged-in register number"""
    print(f"DEBUG: Session data - role: {session.get('role')}, register_number: {session.get('register_number')}, user_id: {session.get('user_id')}")
    
    if session.get("role") != "student" or not session.get("register_number"):
        return jsonify({"error": "Not logged in"}), 401
    
    register_number = session.get("register_number")
    print(f"DEBUG: Loading profile for register_number: {register_number}")
    
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM student_profiles 
        WHERE register_number = ?
    """, (register_number,))
    
    row = cur.fetchone()
    
    if not row:
        conn.close()
        # No existing profile - return empty profile with register number
        return jsonify({
            "register_number": register_number,
            "has_existing_data": False
        })
    
    # Get column names from cursor description
    columns = [desc[0] for desc in cur.description]
    profile = dict(zip(columns, row))
    conn.close()
    
    # Debug: Log what we're getting from database
    print(f"DEBUG: Profile loaded for {register_number}:")
    print(f"  - Available columns: {columns}")
    print(f"  - communication_answers: {repr(profile.get('communication_answers'))}")
    print(f"  - coding_answers: {repr(profile.get('coding_answers'))}")
    print(f"  - marks_file: {repr(profile.get('marks_file'))}")
    print(f"  - communication_score: {profile.get('communication_score')}")
    print(f"  - coding_score: {profile.get('coding_score')}")
    
    # Parse JSON fields
    for field in ['strengths', 'improvement_areas', 'recommendations']:
        if profile.get(field):
            try:
                profile[field] = json.loads(profile[field])
            except:
                profile[field] = []
    
    # Ensure questionnaire answers are available as strings for frontend
    if profile.get('communication_answers'):
        profile['communication_answers'] = profile['communication_answers']
    else:
        profile['communication_answers'] = '[]'
        
    if profile.get('coding_answers'):
        profile['coding_answers'] = profile['coding_answers']
    else:
        profile['coding_answers'] = '[]'
    
    # Add missing fields if they don't exist in database
    if 'marks_file' not in profile:
        profile['marks_file'] = None
    
    profile["has_existing_data"] = True
    
    return jsonify(profile)

@app.route("/api/profile/current", methods=["PUT"])
def update_current_profile():
    """Update current logged-in student's profile"""
    if session.get("role") != "student" or not session.get("register_number"):
        return jsonify({"error": "Not logged in"}), 401
    
    register_number = session.get("register_number")
    return update_profile(register_number)

@app.route("/api/profile/current/marks", methods=["PUT"])
def update_current_marks():
    """Update current logged-in student's marks file"""
    if session.get("role") != "student" or not session.get("register_number"):
        return jsonify({"error": "Not logged in"}), 401
    
    register_number = session.get("register_number")
    
    if "marks_file" not in request.files:
        return jsonify({"success": False, "error": "Marks file is required"}), 400
        
    file = request.files["marks_file"]
    if file.filename == '' or not allowed_marks_file(file.filename):
        return jsonify({"success": False, "error": "Invalid file type. Only PDF, JPG, PNG allowed"}), 400
    
    # Save marks file
    filename = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    path = os.path.join(UPLOAD_DIR, unique_name)
    
    try:
        file.save(path)
    except Exception:
        return jsonify({"success": False, "error": "Failed to save file"}), 500
    
    # Update database
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE student_profiles 
            SET marks_file = ?, updated_at = CURRENT_TIMESTAMP
            WHERE register_number = ?
        """, (unique_name, register_number))
        
        if cur.rowcount == 0:
            return jsonify({"success": False, "error": "Profile not found"}), 404
        
        conn.commit()
        
        return jsonify({
            "success": True,
            "message": "Marks file updated successfully",
            "filename": filename
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": "Failed to update marks file"}), 500
    finally:
        conn.close()

@app.route("/api/profile/current/resume", methods=["PUT"])
def update_current_resume():
    """Update current logged-in student's resume"""
    if session.get("role") != "student" or not session.get("register_number"):
        return jsonify({"error": "Not logged in"}), 401
    
    register_number = session.get("register_number")
    return update_resume(register_number)

@app.route("/api/profile/<student_id>", methods=["GET"])
def get_profile(student_id):
    """Get student profile data"""
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM student_profiles 
        WHERE student_id = ?
    """, (student_id,))
    
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return jsonify({"error": "Profile not found"}), 404
    
    # Convert row to dict
    columns = [desc[0] for desc in cur.description]
    profile = dict(zip(columns, row))
    
    # Parse JSON fields
    for field in ['strengths', 'improvement_areas', 'recommendations']:
        if profile.get(field):
            try:
                profile[field] = json.loads(profile[field])
            except:
                profile[field] = []
    
    return jsonify(profile)

@app.route("/api/profile/<student_id>", methods=["PUT"])
def update_profile(student_id):
    """Update student profile - PRESERVE ALL existing data, only update provided fields"""
    # Use logged-in register number if available
    if session.get("role") == "student" and session.get("register_number"):
        register_number = session.get("register_number")
    else:
        register_number = student_id
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON data"}), 400
    
    print(f"DEBUG: Updating profile for {register_number} with data: {data}")
    
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Get ALL current profile data to preserve everything
        cur.execute("""
            SELECT name, branch, year, cgpa, backlogs, communication_score, coding_score,
                   communication_answers, coding_answers, marks_file, resume_ats_score, 
                   projects, internships, skills_count, strengths, improvement_areas,
                   recommendations, resume_filename, auth_id, student_id, created_at
            FROM student_profiles WHERE register_number = ?
        """, (register_number,))
        
        current_data = cur.fetchone()
        if not current_data:
            return jsonify({"error": "Profile not found"}), 404
        
        # Unpack existing data
        (existing_name, existing_branch, existing_year, existing_cgpa, existing_backlogs,
         existing_comm_score, existing_coding_score, existing_comm_answers, existing_coding_answers,
         existing_marks_file, existing_resume_score, existing_projects, existing_internships,
         existing_skills_count, existing_strengths, existing_improvement_areas, existing_recommendations,
         existing_resume_filename, existing_auth_id, existing_student_id, existing_created_at) = current_data
        
        # Calculate new scores based on updated questionnaire responses
        comm_answers = data.get('communication_answers', [])
        coding_answers = data.get('coding_answers', [])
        
        # Always recalculate communication score if answers provided
        if comm_answers:
            new_comm_score = communication_score(comm_answers)
            print(f"DEBUG: New communication score calculated: {new_comm_score} from answers: {comm_answers}")
        else:
            new_comm_score = existing_comm_score or 0
        
        # Calculate new coding score if answers provided
        if coding_answers:
            q_score = coding_questionnaire_score(coding_answers)
            new_coding_score = coding_score_from_questionnaire(
                q_score, 
                existing_projects or 0,
                existing_skills_count or 0
            )
            print(f"DEBUG: New coding score calculated: {new_coding_score} from questionnaire: {q_score}")
        else:
            new_coding_score = existing_coding_score or 0
        
        # Use provided values or keep existing ones
        final_name = data.get('name', existing_name or '')
        final_branch = data.get('branch', existing_branch or '')
        final_year = data.get('year', existing_year or '')
        final_cgpa = round(float(data.get('cgpa', existing_cgpa or 0)), 2)
        final_backlogs = int(data.get('backlogs', existing_backlogs or 0))
        final_comm_answers = json.dumps(comm_answers) if comm_answers else (existing_comm_answers or '[]')
        final_coding_answers = json.dumps(coding_answers) if coding_answers else (existing_coding_answers or '[]')
        
        # Recalculate v_score with new data
        new_v_score = calculate_v_score(
            final_cgpa,
            new_coding_score,
            new_comm_score,
            existing_resume_score or 0,
            existing_projects or 0,
            existing_internships or 0
        )
        
        # Update profile - ONLY update the fields that can change, preserve everything else
        cur.execute("""
            UPDATE student_profiles 
            SET name = ?, branch = ?, year = ?, 
                cgpa = ?, backlogs = ?, communication_answers = ?, coding_answers = ?,
                communication_score = ?, coding_score = ?, overall_readiness_score = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE register_number = ?
        """, (
            final_name, final_branch, final_year,
            final_cgpa, final_backlogs, final_comm_answers, final_coding_answers,
            new_comm_score, new_coding_score, new_v_score,
            register_number
        ))
        
        print(f"DEBUG: Rows affected: {cur.rowcount}")
        print(f"DEBUG: Preserved data - name: {final_name}, branch: {final_branch}, comm_answers: {final_comm_answers}")
        
        if cur.rowcount == 0:
            return jsonify({"error": "Profile not found"}), 404
        
        conn.commit()
        
        # Determine placement status based on new score
        if new_v_score >= 70:
            placement_status = "Placement Ready"
        elif new_v_score >= 40:
            placement_status = "Medium Risk"
        else:
            placement_status = "High Risk"
        
        return jsonify({
            "message": "Profile updated successfully",
            "communication_score": new_comm_score,
            "coding_score": new_coding_score,
            "overall_readiness_score": new_v_score,
            "placement_status": placement_status
        })
    
    except Exception as e:
        print(f"DEBUG: Error updating profile: {e}")
        return jsonify({"error": f"Update failed: {str(e)}"}), 500
    finally:
        conn.close()

@app.route("/api/profile/<student_id>/resume", methods=["PUT"])
def update_resume(student_id):
    """Update resume and re-analyze - ONLY resume fields, preserve ALL other data"""
    # Use logged-in register number if available
    if session.get("role") == "student" and session.get("register_number"):
        register_number = session.get("register_number")
    else:
        register_number = student_id
        
    if "resume" not in request.files:
        return jsonify({"success": False, "error": "Resume file is required"}), 400
        
    file = request.files["resume"]
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({"success": False, "error": "Invalid file type. Only PDF, DOC, DOCX allowed"}), 400
    
    # Get existing profile data to preserve ALL non-resume fields
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT name, branch, year, cgpa, backlogs, communication_score, coding_score,
               communication_answers, coding_answers, marks_file, strengths, improvement_areas,
               recommendations, auth_id, student_id, created_at
        FROM student_profiles 
        WHERE register_number = ?
    """, (register_number,))
    
    existing = cur.fetchone()
    if not existing:
        conn.close()
        return jsonify({"success": False, "error": "Profile not found"}), 404
    
    # Store ALL existing non-resume data
    (existing_name, existing_branch, existing_year, existing_cgpa, existing_backlogs,
     existing_comm_score, existing_coding_score, existing_comm_answers, existing_coding_answers,
     existing_marks_file, existing_strengths, existing_improvement_areas, existing_recommendations,
     existing_auth_id, existing_student_id, existing_created_at) = existing
    
    print(f"DEBUG: Preserving - name: {existing_name}, comm_answers: {existing_comm_answers}")
    
    # Process new resume
    filename = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    path = os.path.join(UPLOAD_DIR, unique_name)
    file.save(path)
    
    try:
        text = extract_text(path)
        resume_feats = extract_resume_features(text)
        
        # Use new ATS-grade analysis for more accurate metrics
        ats_analysis = ats_grade_resume_analysis(text)
        print(f"DEBUG UPDATE_RESUME: ATS analysis returned projects_count: {ats_analysis['projects_count']}")
        
        # Merge results - prefer skills discovered by extract_resume_features
        # (i.e. resume_feats['skills_list']) when present; otherwise fall
        # back to the ATS-grade count. Keep ATS counts for other metrics.
        num_skills_from_feats = None
        if isinstance(resume_feats.get('skills_list'), (list, tuple)) and len(resume_feats.get('skills_list')) > 0:
            num_skills_from_feats = len(resume_feats.get('skills_list'))

        resume_feats.update({
            'number_of_skills': int(num_skills_from_feats if num_skills_from_feats is not None else ats_analysis.get('skills_count', 0)),
            'num_projects': ats_analysis.get('projects_count', 0),
            'num_internships': ats_analysis.get('internships_count', 0),
            'num_certifications': ats_analysis.get('certifications_count', 0),
            'workshops': ats_analysis.get('workshops_count', 0),
            'events': ats_analysis.get('events_count', 0)
        })
        print(f"DEBUG UPDATE_RESUME: Updated resume_feats num_projects to: {resume_feats['num_projects']}")
        
        new_resume_score = resume_score(resume_feats)
        
        # Calculate new v_score using existing profile data + new resume data
        new_v_score = calculate_v_score(
            existing_cgpa or 0,
            existing_coding_score or 0,
            existing_comm_score or 0,
            new_resume_score,
            resume_feats.get('num_projects', 0),
            resume_feats.get('num_internships', 0)
        )
        
        # Update ONLY resume-dependent fields - NEVER touch preserved fields
        cur.execute("""
            UPDATE student_profiles 
            SET skills_count = ?, projects = ?, internships = ?, certifications = ?,
                workshops = ?, hackathons = ?, resume_ats_score = ?, 
                experience_index = ?, v_score = ?, overall_readiness_score = ?,
                resume_filename = ?, last_uploaded_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE register_number = ?
        """, (
            resume_feats.get('number_of_skills', 0),
            resume_feats.get('num_projects', 0),
            resume_feats.get('num_internships', 0),
            resume_feats.get('num_certifications', 0),
            resume_feats.get('workshops', 0),
            resume_feats.get('hackathons', 0),
            new_resume_score,
            resume_feats.get('num_projects', 0) + resume_feats.get('num_internships', 0),
            new_v_score,
            new_v_score,
            filename,
            register_number
        ))
        
        conn.commit()
        
        return jsonify({
            "success": True,
            "message": "Resume updated successfully",
            "resume_score": new_resume_score,
            "v_score": new_v_score,
            "final_score": new_v_score,
            "overall_readiness_score": new_v_score,
            **resume_feats
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": "Failed to process resume"}), 400
    finally:
        conn.close()

@app.route("/api/analytics/current", methods=["GET"])
def get_current_user_analytics():
    """Get analytics data for currently logged-in student"""
    if session.get("role") != "student" or not session.get("register_number"):
        return jsonify({"error": "Not logged in"}), 401
    
    register_number = session.get("register_number")
    return get_analytics(register_number)

@app.route("/api/analytics/<student_id>", methods=["GET"])
def get_analytics(student_id):
    """Get analytics data for student"""
    # If user is logged in, use their register number; otherwise use provided student_id
    if session.get("role") == "student" and session.get("register_number"):
        register_number = session.get("register_number")
    else:
        register_number = student_id
    
    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT * FROM student_profiles 
        WHERE register_number = ?
    """, (register_number,))
    
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return jsonify({"error": "Profile not found. Please run Analyze Profile first."}), 404
    
    # Convert to analytics format - match actual database schema
    columns = ["id", "student_id", "name", "register_number", "branch", "year",
               "cgpa", "backlogs", "communication_score", "coding_score", "skills_count", "projects", 
               "internships", "certifications", "events", "workshops", "hackathons", "resume_ats_score", 
               "experience_index", "overall_readiness_score", "v_score", "strengths", "improvement_areas", 
               "recommendations", "resume_filename", "last_uploaded_at", "created_at", "updated_at", 
               "auth_id", "communication_answers", "coding_answers"]
    
    profile = dict(zip(columns, row))
    
    # Use overall_readiness_score as primary source
    overall_score = profile.get('overall_readiness_score') or profile.get('v_score') or 0
    overall_score = round(min(100, max(0, float(overall_score))), 2)
    
    analytics = {
        "name": profile['name'],
        "roll_no": profile['register_number'],
        "register_number": profile['register_number'],
        "branch": profile['branch'],
        "year": profile['year'],
        "cgpa": profile['cgpa'],
        "backlogs": profile.get('backlogs', 0),
        "preferred_domain": profile.get('preferred_domain', ''),
        
        # Use overall_readiness_score for all displays
        "overall_readiness_score": overall_score,
        "v_score": overall_score,
        "final_score": overall_score,
        "overall_readiness": overall_score,
        "placement_status": "Placement Ready" if overall_score >= 70 else "Medium Risk" if overall_score >= 40 else "High Risk",
        "risk_flag": overall_score < 40,
        
        "breakdown": {
            "communication": profile['communication_score'] or 0,
            "coding": profile['coding_score'] or 0,
            "resume": profile['resume_ats_score'] or 0,
            "participation": ((profile['events'] or 0) + (profile['workshops'] or 0) + (profile['hackathons'] or 0)) * 5
        },
        
        # Individual component scores for consistency
        "communication_score": profile['communication_score'],
        "coding_questionnaire_score": profile.get('coding_questionnaire_score', 0),
        "resume_boost": min(10, profile['projects'] * 3 + profile['skills_count']),
        "coding_score": profile['coding_score'],
        "resume_score": profile['resume_ats_score'],
        "resume_ats_score": profile['resume_ats_score'],
        "events": profile['events'],
        "workshops": profile['workshops'],
        "hackathons": profile['hackathons'],
        "resume_metrics": {
            "skills_count": profile['skills_count'],
            "projects": profile['projects'],
            "internships": profile['internships'],
            "certifications": profile['certifications'],
            "events": profile['events'],
            "workshops": profile['workshops'],
            "hackathons": profile['hackathons']
        },
        "experience_index": profile['experience_index'],
        "last_updated": profile['updated_at']
    }
    
    # Parse JSON fields
    for field in ['strengths', 'improvement_areas', 'recommendations']:
        if profile.get(field):
            try:
                analytics[field] = json.loads(profile[field])
            except:
                analytics[field] = []
    
    return jsonify(analytics)


@app.route("/api/resume/ats-analysis", methods=["POST"])
def ats_resume_analysis():
    """
    ATS-grade resume analysis endpoint.
    Accepts multipart form with resume file and optional job description.
    Returns structured metrics in exact JSON format.
    """
    if "resume" not in request.files:
        return jsonify({"error": "Resume file is required"}), 400

    file = request.files["resume"]
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Only PDF, DOC, DOCX allowed"}), 400
        
    # Save file temporarily
    filename = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)
    
    try:
        file.save(save_path)
        
        # Extract text from resume
        resume_text = extract_text(save_path)
        
        # Get optional job description
        job_description = request.form.get('job_description', '')
        
        # Perform ATS-grade analysis
        analysis_result = ats_grade_resume_analysis(resume_text, job_description if job_description else None)
        
        # Clean up temporary file
        try:
            os.remove(save_path)
        except:
            pass
        
        return jsonify(analysis_result)
        
    except Exception as e:
        # Clean up on error
        try:
            os.remove(save_path)
        except:
            pass
        return jsonify({"error": "Failed to process resume file"}), 400


@app.route("/api/student/profile/analyze", methods=["POST"])
def profile_analyze():
    """
    Analyze student profile and SAVE to database. Returns analysis + saves complete profile.
    """
    # Save resume
    if "resume" not in request.files:
        return jsonify({"error": "Resume file is required"}), 400

    file = request.files["resume"]
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Only PDF, DOC, DOCX allowed"}), 400
        
    filename = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)
    
    # Handle marks file if provided
    marks_filename = None
    if "marks_file" in request.files:
        marks_file = request.files["marks_file"]
        if marks_file.filename != '' and allowed_marks_file(marks_file.filename):
            marks_filename = secure_filename(marks_file.filename)
            marks_unique_name = f"{uuid.uuid4().hex}_{marks_filename}"
            marks_save_path = os.path.join(UPLOAD_DIR, marks_unique_name)
            try:
                marks_file.save(marks_save_path)
                marks_filename = marks_unique_name
            except Exception:
                marks_filename = None
    
    try:
        file.save(save_path)
    except Exception:
        return jsonify({"error": "Failed to save file"}), 500

    # Optional job description for ATS scoring
    job_description = request.form.get('job_description', '')

    # Extract resume features using both old and new methods
    try:
        text = extract_text(save_path)
        resume_feats = extract_resume_features(text)
        
        # Use new ATS-grade analysis for more accurate metrics
        ats_analysis = ats_grade_resume_analysis(text, job_description if job_description else None)
        print(f"DEBUG PROFILE_ANALYZE: ATS analysis returned projects_count: {ats_analysis['projects_count']}")
        
        # Merge results - prefer skills discovered by extract_resume_features
        # (i.e. resume_feats['skills_list']) when present; otherwise fall
        # back to the ATS-grade count. Keep ATS counts for other metrics.
        num_skills_from_feats = None
        if isinstance(resume_feats.get('skills_list'), (list, tuple)) and len(resume_feats.get('skills_list')) > 0:
            num_skills_from_feats = len(resume_feats.get('skills_list'))

        resume_feats.update({
            'number_of_skills': int(num_skills_from_feats if num_skills_from_feats is not None else ats_analysis.get('skills_count', 0)),
            'num_projects': ats_analysis.get('projects_count', 0),
            'num_internships': ats_analysis.get('internships_count', 0),
            'num_certifications': ats_analysis.get('certifications_count', 0),
            'workshops': ats_analysis.get('workshops_count', 0),
            'events': ats_analysis.get('events_count', 0)
        })
        print(f"DEBUG PROFILE_ANALYZE: Updated resume_feats num_projects to: {resume_feats['num_projects']}")
        
    except Exception:
        return jsonify({"error": "Failed to process resume file"}), 400

    # Parse form fields
    try:
        comm_answers = json.loads(request.form.get("communication_answers", "[]"))
    except json.JSONDecodeError:
        comm_answers = []

    try:
        coding_answers = json.loads(request.form.get("coding_answers", "[]"))
    except json.JSONDecodeError:
        coding_answers = []

    # personal / academic
    name = request.form.get("name", "")
    roll_no = request.form.get("roll_no", "")
    year = request.form.get("year", "")
    branch = request.form.get("branch", "")
    cgpa_raw = request.form.get("cgpa", "0")
    try:
        cgpa = round(float(cgpa_raw), 2)
        if cgpa < 0 or cgpa > 10:
            cgpa = 0.0
    except (ValueError, TypeError):
        cgpa = 0.0
        
    try:
        backlogs = int(request.form.get("backlogs", "0"))
        if backlogs < 0:
            backlogs = 0
    except (ValueError, TypeError):
        backlogs = 0
        
    preferred_domain = request.form.get("domain", "")

    comm_score = communication_score(comm_answers)
    q_score = coding_questionnaire_score(coding_answers)
    
    # Calculate resume boost separately for display
    resume_boost = min(10, resume_feats.get("num_projects", 0) * 3 + resume_feats.get("number_of_skills", 0))
    
    coding_final = coding_score_from_questionnaire(q_score, resume_feats.get("num_projects", 0), resume_feats.get("number_of_skills", 0))
    resume_s = resume_score(resume_feats)
    
    # ML PREDICTION for placement status (SINGLE SOURCE OF TRUTH)
    ml_features = {
        "cgpa": cgpa,
        "coding_score": coding_final,
        "communication_score": comm_score,
        "resume_score": resume_s,
        "num_projects": resume_feats.get('num_projects', 0),
        "number_of_skills": resume_feats.get('number_of_skills', 0)
    }
    
    # CALCULATE V_SCORE ONCE - SINGLE SOURCE OF TRUTH
    v_score_percent = calculate_v_score(
        cgpa, coding_final, comm_score, resume_s, 
        resume_feats.get('num_projects', 0), 
        resume_feats.get('num_internships', 0)
    )
        
    # Determine placement status based on ML v_score
    if v_score_percent >= 70:
        placement_status = "Placement Ready"
    elif v_score_percent >= 40:
        placement_status = "Medium Risk"
    else:
        placement_status = "High Risk"
    
    # AUTO-EMAIL TPO for High-Risk Students (v_score < 40%)
    print(f"DEBUG: Checking email alert - v_score: {v_score_percent}%, name: {name}, roll_no: {roll_no}")
    if v_score_percent < 40 and name and roll_no:
        print(f"DEBUG: Triggering email alert for high-risk student")
        try:
            conn_tpo = get_connection()
            cur_tpo = conn_tpo.cursor()
            cur_tpo.execute("SELECT email FROM tpo_auth LIMIT 1")
            tpo_result = cur_tpo.fetchone()
            conn_tpo.close()
            
            if tpo_result:
                tpo_email = tpo_result[0]
                # Use ML model v_score for email (SINGLE SOURCE OF TRUTH)
                student_payload = f"Name: {name}\nRegister Number: {roll_no}\nDepartment: {branch}\nPlacement Readiness Score: {v_score_percent:.1f}%\nStatus: {placement_status}\nLabel: HIGH RISK – Requires Immediate Attention"
                print(f"DEBUG: Sending email to {tpo_email} for student {name} ({roll_no})")
                send_tpo_email(tpo_email, student_payload, v_score_percent)
            else:
                print("DEBUG: No TPO email found in database")
        except Exception as e:
            print(f"Email sending failed: {e}")
    else:
        print(f"DEBUG: Email not triggered - conditions not met")
    
    ats = {}
    if job_description:
        try:
            ats = ats_score(job_description, resume_feats.get('resume_text', ''), resume_feats)
        except Exception:
            ats = {}

    # Generate insights (simple logic)
    strengths = []
    improvement_areas = []
    recommendations = []
    
    if comm_score >= 70:
        strengths.append("Strong communication skills")
    else:
        improvement_areas.append("Communication skills")
        recommendations.append("Practice mock interviews and group discussions")
    
    if coding_final >= 70:
        strengths.append("Good coding abilities")
    else:
        improvement_areas.append("Coding skills")
        recommendations.append("Solve more coding problems on platforms like LeetCode")
    
    if resume_s >= 70:
        strengths.append("Well-structured resume")
    else:
        improvement_areas.append("Resume quality")
        recommendations.append("Add more projects and relevant skills to your resume")
    
    # SAVE TO DATABASE (use logged-in register number)
    if session.get("role") == "student" and session.get("register_number"):
        logged_register_number = session.get("register_number")
        
        # Override roll_no with logged-in register number for consistency
        roll_no = logged_register_number
        
        conn = get_connection()
        cur = conn.cursor()
        
        try:
            # Use logged-in register number as student_id
            student_id = logged_register_number
            auth_id = session.get("user_id") or 1
            
            # Check if profile exists
            cur.execute("SELECT id FROM student_profiles WHERE register_number = ?", (logged_register_number,))
            existing = cur.fetchone()
            
            if existing:
                # UPDATE existing profile
                cur.execute("""
                    UPDATE student_profiles 
                    SET student_id = ?, name = ?, branch = ?, year = ?,
                        cgpa = ?, backlogs = ?, communication_score = ?, coding_score = ?,
                        skills_count = ?, projects = ?, internships = ?, certifications = ?,
                        workshops = ?, hackathons = ?, resume_ats_score = ?, 
                        experience_index = ?, overall_readiness_score = ?, v_score = ?,
                        strengths = ?, improvement_areas = ?, recommendations = ?,
                        resume_filename = ?, marks_file = ?, communication_answers = ?, coding_answers = ?,
                        last_uploaded_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE register_number = ?
                """, (
                    student_id, name, branch, year,
                    cgpa, backlogs, comm_score, coding_final,
                    resume_feats.get('number_of_skills', 0),
                    resume_feats.get('num_projects', 0),
                    resume_feats.get('num_internships', 0),
                    resume_feats.get('num_certifications', 0),
                    resume_feats.get('workshops', 0),
                    resume_feats.get('hackathons', 0),
                    resume_s,
                    resume_feats.get('num_projects', 0) + resume_feats.get('num_internships', 0),
                    v_score_percent, v_score_percent,
                    json.dumps(strengths),
                    json.dumps(improvement_areas),
                    json.dumps(recommendations),
                    filename,
                    marks_filename,
                    json.dumps(comm_answers),
                    json.dumps(coding_answers),
                    logged_register_number
                ))
                print(f"DEBUG: Updated profile with comm_answers: {json.dumps(comm_answers)}, coding_answers: {json.dumps(coding_answers)}")
            else:
                # INSERT new profile
                cur.execute("""
                    INSERT INTO student_profiles (
                        student_id, name, register_number, branch, year,
                        cgpa, backlogs, communication_score, coding_score,
                        skills_count, projects, internships, certifications, workshops, hackathons,
                        resume_ats_score, experience_index, overall_readiness_score, v_score,
                        strengths, improvement_areas, recommendations,
                        resume_filename, marks_file, communication_answers, coding_answers,
                        last_uploaded_at, auth_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """, (
                    student_id, name, logged_register_number, branch, year,
                    cgpa, backlogs, comm_score, coding_final,
                    resume_feats.get('number_of_skills', 0),
                    resume_feats.get('num_projects', 0),
                    resume_feats.get('num_internships', 0),
                    resume_feats.get('num_certifications', 0),
                    resume_feats.get('workshops', 0),
                    resume_feats.get('hackathons', 0),
                    resume_s,
                    resume_feats.get('num_projects', 0) + resume_feats.get('num_internships', 0),
                    v_score_percent, v_score_percent,
                    json.dumps(strengths),
                    json.dumps(improvement_areas),
                    json.dumps(recommendations),
                    filename,
                    marks_filename,
                    json.dumps(comm_answers),
                    json.dumps(coding_answers),
                    auth_id
                ))
                print(f"DEBUG: Inserted new profile with comm_answers: {json.dumps(comm_answers)}, coding_answers: {json.dumps(coding_answers)}")
            
            conn.commit()
        except Exception as e:
            print(f"Database save error: {e}")
            # Continue without failing the analysis
        finally:
            conn.close()

    result = {
        "name": name,
        "roll_no": roll_no,  # This will be the logged-in register number
        "year": year,
        "branch": branch,
        "cgpa": cgpa,
        "backlogs": backlogs,
        "preferred_domain": preferred_domain,

        "communication_score": comm_score,
        "coding_questionnaire_score": q_score,
        "resume_boost": resume_boost,
        "coding_score": coding_final,
        "resume_score": resume_s,
        "overall_readiness_score": v_score_percent,
        
        "v_score": v_score_percent,
        "final_score": v_score_percent,
        "placement_status": placement_status,
        "risk_flag": v_score_percent < 50,
        
        "breakdown": {
            "coding": coding_final,
            "communication": comm_score,
            "resume": resume_s,
            "participation": (resume_feats.get('workshops', 0) + resume_feats.get('hackathons', 0)) * 10
        },
        
        "strengths": strengths,
        "improvement_areas": improvement_areas,
        "recommendations": recommendations,

        **resume_feats,
        "ats": ats
    }

    return jsonify(result)

# ===============================
# TPO ANALYTICS ENDPOINTS
# ===============================
@app.route("/api/students/year/<year>", methods=["GET"])
def get_students_by_year(year):
    """Get students by year for TPO analytics"""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT COALESCE(name, '') as name, 
                   COALESCE(register_number, '') as register_number, 
                   COALESCE(branch, '') as branch, 
                   COALESCE(year, '') as year, 
                   COALESCE(cgpa, 0) as cgpa, 
                   COALESCE(backlogs, 0) as backlogs, 
                   COALESCE(communication_score, 0) as communication_score, 
                   COALESCE(coding_score, 0) as coding_score, 
                   COALESCE(overall_readiness_score, 0) as overall_readiness_score
            FROM student_profiles 
            WHERE year = ? OR year = ?
            ORDER BY 
                CASE COALESCE(branch, '')
                    WHEN 'CSE' THEN 1
                    WHEN 'CSE (Artificial Intelligence)' THEN 2
                    WHEN 'CSE (Data Science)' THEN 3
                    WHEN 'ECE' THEN 4
                    WHEN 'EEE' THEN 5
                    WHEN 'CIV' THEN 6
                    WHEN 'CIVIL' THEN 6
                    WHEN 'MECH' THEN 7
                    WHEN 'MECHANICAL' THEN 7
                    ELSE 8
                END,
                COALESCE(name, '')
        """, (year, year.replace('st', '').replace('nd', '').replace('rd', '').replace('th', '')))
        
        rows = cur.fetchall()
        
        # Convert to list of dictionaries
        students = []
        for row in rows:
            student = {
                "name": row[0],
                "register_number": row[1],
                "branch": row[2],
                "year": row[3],
                "cgpa": row[4],
                "backlogs": row[5],
                "communication_score": row[6],
                "coding_score": row[7],
                "overall_readiness_score": row[8]
            }
            students.append(student)
        
        return jsonify(students)
        
    except Exception as e:
        print(f"Error fetching students by year: {e}")
        return jsonify({"error": "Failed to fetch students"}), 500
    finally:
        conn.close()

@app.route("/api/students/year/<year>/stats", methods=["GET"])
def get_year_stats(year):
    """Get statistics for a specific year"""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Get total students and average readiness - include all students
        cur.execute("""
            SELECT COUNT(*) as total_students,
                   AVG(CASE WHEN v_score IS NOT NULL THEN 
                       CASE WHEN v_score > 1.0 THEN v_score ELSE v_score * 100 END 
                       ELSE 0 END) as avg_readiness,
                   COUNT(CASE WHEN v_score IS NOT NULL AND v_score < 0.5 THEN 1 END) as high_risk
            FROM student_profiles 
            WHERE year = ? OR year = ?
        """, (year, year.replace('st', '').replace('nd', '').replace('rd', '').replace('th', '')))
        
        row = cur.fetchone()
        print(f"DEBUG: Year {year} stats - Total: {row[0]}, Avg: {row[1]}, High Risk: {row[2]}")
        
        if row and row[0] > 0:
            stats = {
                "total_students": row[0] or 0,
                "avg_readiness": round(row[1] or 0, 1),
                "high_risk": row[2] or 0
            }
        else:
            stats = {
                "total_students": 0,
                "avg_readiness": 0,
                "high_risk": 0
            }
        
        return jsonify(stats)
        
    except Exception as e:
        print(f"Error fetching year stats: {e}")
        return jsonify({"error": "Failed to fetch statistics"}), 500
    finally:
        conn.close()

@app.route('/api/students/branch/<branch>', methods=['GET'])
def get_students_by_branch(branch):
    """Get students by branch for department analytics"""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Map frontend branch codes to database names
        branch_mapping = {
            'CSE': 'CSE',
            'CSE-AI': 'CSE (Artificial Intelligence)',
            'CSE-DS': 'CSE (Data Science)',
            'ECE': 'ECE',
            'EEE': 'EEE',
            'CIVIL': 'CIVIL',
            'MECH': 'MECHANICAL'
        }
        
        db_branch = branch_mapping.get(branch, branch)
        
        cur.execute("""
            SELECT name, register_number, branch, year, 
                   cgpa, backlogs, communication_score, coding_score, overall_readiness_score
            FROM student_profiles 
            WHERE branch = ?
            ORDER BY 
                CASE 
                    WHEN year IN ('1st', '1') THEN 1
                    WHEN year IN ('2nd', '2') THEN 2
                    WHEN year IN ('3rd', '3') THEN 3
                    WHEN year IN ('4th', '4') THEN 4
                    ELSE 5
                END,
                name
        """, (db_branch,))
        
        rows = cur.fetchall()
        
        # Convert to list of dictionaries
        students = []
        for row in rows:
            student = {
                "name": row[0],
                "register_number": row[1],
                "branch": row[2],
                "year": row[3],
                "cgpa": row[4],
                "backlogs": row[5],
                "communication_score": row[6],
                "coding_score": row[7],
                "overall_readiness_score": row[8]
            }
            students.append(student)
        
        return jsonify(students)
        
    except Exception as e:
        print(f"Error fetching students by branch: {e}")
        return jsonify({"error": "Failed to fetch students"}), 500
    finally:
        conn.close()

@app.route('/api/students/college/stats', methods=['GET'])
def get_college_stats():
    """Get college-wide statistics"""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Get total students
        cur.execute("SELECT COUNT(*) FROM student_profiles")
        total_students = cur.fetchone()[0] or 0
        
        # Get unique departments
        cur.execute("SELECT COUNT(DISTINCT branch) FROM student_profiles WHERE branch IS NOT NULL AND branch != ''")
        departments = cur.fetchone()[0] or 0
        
        # Get unique years (only count valid years)
        cur.execute("SELECT COUNT(DISTINCT CASE WHEN year IN ('1st', '1') THEN '1st' WHEN year IN ('2nd', '2') THEN '2nd' WHEN year IN ('3rd', '3') THEN '3rd' WHEN year IN ('4th', '4') THEN '4th' END) FROM student_profiles WHERE year IN ('1st', '1', '2nd', '2', '3rd', '3', '4th', '4')")
        years = cur.fetchone()[0] or 0
        
        # Get average readiness using overall_readiness_score
        cur.execute("SELECT AVG(CASE WHEN overall_readiness_score IS NOT NULL THEN overall_readiness_score ELSE 0 END) FROM student_profiles WHERE overall_readiness_score IS NOT NULL")
        avg_readiness_raw = cur.fetchone()[0] or 0
        avg_readiness = round(avg_readiness_raw, 1)
        
        # Get high performers (overall_readiness_score > 70)
        cur.execute("SELECT COUNT(*) FROM student_profiles WHERE overall_readiness_score > 70")
        high_performers = cur.fetchone()[0] or 0
        
        # Get at-risk students (overall_readiness_score < 40)
        cur.execute("SELECT COUNT(*) FROM student_profiles WHERE overall_readiness_score < 40")
        at_risk = cur.fetchone()[0] or 0
        
        # Calculate high risk percentage
        high_risk_percentage = round((at_risk / total_students) * 100, 2) if total_students > 0 else 0
        
        stats = {
            "total_students": total_students,
            "departments": departments,
            "years": years,
            "avg_readiness": avg_readiness,
            "high_performers": high_performers,
            "at_risk": at_risk,
            "high_risk_percentage": high_risk_percentage
        }
        
        return jsonify(stats)
        
    except Exception as e:
        print(f"Error fetching college stats: {e}")
        return jsonify({"error": "Failed to fetch statistics"}), 500
    finally:
        conn.close()

@app.route('/api/students/college/all', methods=['GET'])
def get_all_students():
    """Get all students for college-wide analytics"""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT name, register_number, branch, year, 
                   cgpa, backlogs, communication_score, coding_score, overall_readiness_score
            FROM student_profiles 
            ORDER BY 
                CASE branch
                    WHEN 'CSE' THEN 1
                    WHEN 'CSE (Artificial Intelligence)' THEN 2
                    WHEN 'CSE (Data Science)' THEN 3
                    WHEN 'ECE' THEN 4
                    WHEN 'EEE' THEN 5
                    WHEN 'CIVIL' THEN 6
                    WHEN 'MECHANICAL' THEN 7
                    ELSE 8
                END,
                CASE 
                    WHEN year IN ('1st', '1') THEN 1
                    WHEN year IN ('2nd', '2') THEN 2
                    WHEN year IN ('3rd', '3') THEN 3
                    WHEN year IN ('4th', '4') THEN 4
                    ELSE 5
                END,
                name
        """)
        
        rows = cur.fetchall()
        
        # Convert to list of dictionaries
        students = []
        for row in rows:
            student = {
                "name": row[0],
                "register_number": row[1],
                "branch": row[2],
                "year": row[3],
                "cgpa": row[4],
                "backlogs": row[5],
                "communication_score": row[6],
                "coding_score": row[7],
                "overall_readiness_score": row[8]
            }
            students.append(student)
        
        return jsonify(students)
        
    except Exception as e:
        print(f"Error fetching all students: {e}")
        return jsonify({"error": "Failed to fetch students"}), 500
    finally:
        conn.close()

@app.route('/api/upload/csv', methods=['POST'])
def upload_csv():
    """Upload and process CSV file for student data"""
    if 'csvFile' not in request.files:
        return jsonify({"success": False, "error": "No CSV file provided"}), 400
    
    file = request.files['csvFile']
    if file.filename == '' or not file.filename.endswith('.csv'):
        return jsonify({"success": False, "error": "Please select a valid CSV file"}), 400
    
    try:
        # Use pandas to properly parse CSV with quoted fields
        import io
        csv_content = file.read().decode('utf-8')
        df = pd.read_csv(io.StringIO(csv_content))
        
        if df.empty:
            return jsonify({"success": False, "error": "CSV file is empty"}), 400
        
        # Convert column names to lowercase for matching
        df.columns = df.columns.str.strip().str.lower()
        
        # Required columns for student_profiles table
        required_columns = [
            'name', 'register_number', 'branch', 'year', 'cgpa', 'backlogs',
            'communication_score', 'coding_score', 'overall_readiness_score'
        ]
        
        # Check if all required columns are present
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return jsonify({
                "success": False, 
                "error": f"CSV file is missing required columns: {', '.join(missing_columns)}. Please ensure your CSV contains all required fields."
            }), 400
        
        # Process data rows
        conn = get_connection()
        cur = conn.cursor()
        
        inserted_count = 0
        updated_count = 0
        
        for index, row in df.iterrows():
            try:
                # Validate and convert data types
                cgpa = float(row.get('cgpa', 0))
                backlogs = int(row.get('backlogs', 0))
                comm_score = float(row.get('communication_score', 0))
                coding_score = float(row.get('coding_score', 0))
                readiness_score = float(row.get('overall_readiness_score', 0))
                
                # Check if student already exists
                cur.execute("SELECT id FROM student_profiles WHERE register_number = ?", 
                           (row['register_number'],))
                existing = cur.fetchone()
                
                if existing:
                    # Update existing student
                    cur.execute("""
                        UPDATE student_profiles 
                        SET name = ?, branch = ?, year = ?, cgpa = ?, backlogs = ?,
                            communication_score = ?, coding_score = ?, overall_readiness_score = ?,
                            skills_count = ?, projects = ?, internships = ?, certifications = ?,
                            events = ?, workshops = ?, hackathons = ?, resume_ats_score = ?,
                            experience_index = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE register_number = ?
                    """, (
                        row['name'], row['branch'], row['year'],
                        cgpa, backlogs, comm_score, coding_score, readiness_score,
                        int(row.get('skills_count', 0)), int(row.get('projects', 0)), 
                        int(row.get('internships', 0)), int(row.get('certifications', 0)),
                        int(row.get('events', 0)), int(row.get('workshops', 0)), 
                        int(row.get('hackathons', 0)), int(row.get('resume_ats_score', 0)),
                        int(row.get('experience_index', 0)), row['register_number']
                    ))
                    updated_count += 1
                else:
                    # Insert new student
                    cur.execute("""
                        INSERT INTO student_profiles (
                            student_id, name, register_number, branch, year, cgpa, backlogs,
                            communication_score, coding_score, overall_readiness_score,
                            v_score, skills_count, projects, internships, certifications,
                            events, workshops, hackathons, resume_ats_score, experience_index
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row['register_number'], row['name'], row['register_number'],
                        row['branch'], row['year'], cgpa, backlogs,
                        comm_score, coding_score, readiness_score, readiness_score / 100,
                        int(row.get('skills_count', 0)), int(row.get('projects', 0)), 
                        int(row.get('internships', 0)), int(row.get('certifications', 0)),
                        int(row.get('events', 0)), int(row.get('workshops', 0)), 
                        int(row.get('hackathons', 0)), int(row.get('resume_ats_score', 0)), 
                        int(row.get('experience_index', 0))
                    ))
                    inserted_count += 1
                    
            except (ValueError, KeyError) as e:
                print(f"Error processing row {index}: {e}")
                continue  # Skip invalid rows
        
        conn.commit()
        conn.close()
        
        if inserted_count == 0 and updated_count == 0:
            return jsonify({"success": False, "error": "No valid data rows found in CSV file"}), 400
        
        message = f"Successfully processed CSV file! Inserted {inserted_count} new students, updated {updated_count} existing students."
        return jsonify({"success": True, "message": message})
        
    except Exception as e:
        print(f"Error processing CSV: {e}")
        return jsonify({"success": False, "error": "Failed to process CSV file. Please check the file format."}), 500

@app.route('/api/debug/students/<year>', methods=['GET'])
def debug_students_by_year(year):
    """Debug endpoint to see all students for a specific year"""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT name, register_number, branch, year
            FROM student_profiles 
            WHERE year = ?
            ORDER BY name
        """, (year,))
        
        rows = cur.fetchall()
        students = []
        for row in rows:
            students.append({
                "name": row[0],
                "register_number": row[1], 
                "branch": row[2],
                "year": row[3]
            })
        
        return jsonify(students)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route("/api/students/cohort/<year>/<branch>", methods=["GET"])
def get_students_by_cohort(year, branch):
    """Get students by year and branch for cohort analytics"""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Map frontend branch codes to database branch names
        branch_mapping = {
            'CSE': 'CSE',
            'CSE-AI': 'CSE (Artificial Intelligence)',
            'CSE-DS': 'CSE (Data Science)',
            'ECE': 'ECE',
            'EEE': 'EEE',
            'CIVIL': 'CIVIL',
            'MECH': 'MECHANICAL'
        }
        
        db_branch = branch_mapping.get(branch, branch)
        
        cur.execute("""
            SELECT name, register_number, branch, year, 
                   cgpa, backlogs, communication_score, coding_score, overall_readiness_score
            FROM student_profiles 
            WHERE (year = ? OR year = ?) AND branch = ?
            ORDER BY name
        """, (year, year.replace('st', '').replace('nd', '').replace('rd', '').replace('th', ''), db_branch))
        
        rows = cur.fetchall()
        
        # Convert to list of dictionaries
        students = []
        for row in rows:
            student = {
                "name": row[0],
                "register_number": row[1],
                "branch": row[2],
                "year": row[3],
                "cgpa": row[4],
                "backlogs": row[5],
                "communication_score": row[6],
                "coding_score": row[7],
                "overall_readiness_score": row[8]
            }
            students.append(student)
        
        return jsonify(students)
        
    except Exception as e:
        print(f"Error fetching cohort data: {e}")
        return jsonify({"error": "Failed to fetch cohort data"}), 500
    finally:
        conn.close()

# ===============================
# ML PREDICTION
# ===============================
@app.route("/api/predict", methods=["POST"])
def predict():
    payload = request.get_json()
    if not payload:
        return jsonify({"error": "Invalid JSON data"}), 400

    try:
        X = create_features_from_input(payload)
        X_scaled = scaler.transform(X)
        X_sel = selector.transform(X_scaled)

        proba = float(model.predict_proba(X_sel)[0, 1])
        prediction = "Placed" if proba >= 0.5 else "Not Placed"

        if payload.get("tpo_email") and proba < ALERT_THRESHOLD:
            try:
                send_tpo_email(payload["tpo_email"], payload, proba)
            except Exception:
                pass

        return jsonify({
            "prediction": prediction,
            "probability": proba
        })
    except Exception:
        return jsonify({"error": "Prediction failed"}), 500

# ===============================
# DEBUG
# ===============================
@app.route("/_debug/users")
def debug_users():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, email FROM students_auth")
    rows = cur.fetchall()
    conn.close()
    return jsonify(rows)

# ===============================
# FRONTEND
# ===============================
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    requested = FRONTEND_DIR / path
    if path and requested.exists():
        return send_from_directory(FRONTEND_DIR, path)
    return send_from_directory(FRONTEND_DIR, "landing_page.html")

# ===============================
# RUN
# ===============================
if __name__ == "__main__":
    app.run(debug=True)
