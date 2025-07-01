import streamlit as st
from streamlit.errors import StreamlitAPIException
import os
import re
import docx
import spacy
import base64
import pandas as pd
import requests
import uuid
import json
from typing import List
from datetime import datetime
from pdfminer.high_level import extract_text

# --- Config ---
UPLOAD_DIR = "uploaded_resumes"
EXCEL_DB = "screening_results.xlsx"
USER_DB_FILE = "user_db.json"
os.makedirs(UPLOAD_DIR, exist_ok=True)
nlp = spacy.load("en_core_web_sm")

RAPIDAPI_KEY = "12e26509b4mshc2f286e27ccb5e7p16203djsn27eec721433f"

def load_user_db():
    if os.path.exists(USER_DB_FILE):
        with open(USER_DB_FILE, "r") as f:
            data = json.load(f)
    else:
        data = {}
    if "admin" not in data:
        data["admin"] = {"password": "adminpass", "role": "Admin"}
    return data

USER_DB = load_user_db()

def save_user_db():
    with open(USER_DB_FILE, "w") as f:
        json.dump(USER_DB, f)

def generate_unique_filename(original_name):
    base, ext = os.path.splitext(original_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:6]
    return f"{base}_{timestamp}_{unique_id}{ext}"

def save_uploaded_file(uploaded_file):
    unique_name = generate_unique_filename(uploaded_file.name)
    file_path = os.path.join(UPLOAD_DIR, unique_name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return unique_name

def read_pdf(file_path: str) -> str:
    try:
        return extract_text(file_path)
    except Exception as e:
        return f"[Error reading PDF: {e}]"

def read_docx(file_path: str) -> str:
    doc = docx.Document(file_path)
    return "\n".join([p.text for p in doc.paragraphs])

def extract_skills(text: str) -> List[str]:
    doc = nlp(text)
    candidates = [chunk.text.lower() for chunk in doc.noun_chunks if len(chunk.text) > 1]
    candidates += [token.text.lower() for token in doc if token.pos_ in ("PROPN","NOUN") and len(token.text) > 1]
    return list(set(candidates))

def score_resume(resume_text: str, skills: List[str]) -> float:
    matches = sum(1 for skill in skills if re.search(rf"\b{re.escape(skill)}\b", resume_text, re.IGNORECASE))
    return matches / len(skills) * 100 if skills else 0

def highlight_text(text: str, skills: List[str]) -> str:
    for skill in sorted(skills, key=len, reverse=True):
        text = re.sub(
            rf"\b({re.escape(skill)})\b",
            r"<mark style='background:#fee2e2; padding:0.1rem 0.2rem; border-radius:0.2rem;'>\1</mark>",
            text,
            flags=re.IGNORECASE,
        )
    return text

def extract_email(text: str) -> str:
    emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    return emails[0] if emails else "Not found"

def extract_phone(text: str) -> str:
    phones = re.findall(r"(\+?\d[\d\s-]{7,}\d)", text)
    return phones[0] if phones else "Not found"

def get_base64_img(img_path):
    with open(img_path, "rb") as img_file:
        encoded = base64.b64encode(img_file.read()).decode()
    return f"data:image/png;base64,{encoded}"

def get_jobs(query, location):
    url = "https://jsearch.p.rapidapi.com/search"
    params = {
        "query": f"{query} in {location}",
        "page": "1",
        "num_pages": "1"
    }
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
    }

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json().get("data", [])
    else:
        st.error(f"❌ API Error {response.status_code}: {response.text}")
        return []

# --- Pages ---
def login():
    st.title("🔐 Friendly Hire Portal")
    tab1, tab2 = st.tabs(["Log In", "Sign Up"])

    with tab1:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            role = st.selectbox("Login as", ["Applicant", "Employer", "Admin"])
            submit = st.form_submit_button("Log In")

            if submit:
                if username in USER_DB and USER_DB[username]["password"] == password and USER_DB[username]["role"] == role:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.role = role
                    st.success(f"Welcome, {username}! You are logged in as {role}.")
                    st.rerun()
                else:
                    st.error("Invalid username, password, or role.")

    with tab2:
        with st.form("signup_form"):
            new_user = st.text_input("Choose a username")
            new_pass = st.text_input("Choose a password", type="password")
            new_role = st.selectbox("Register as", ["Applicant", "Employer"])
            signup = st.form_submit_button("Sign Up")

            if signup:
                if new_user in USER_DB:
                    st.warning("Username already exists.")
                elif new_user.strip() == "" or new_pass.strip() == "":
                    st.warning("Username and password cannot be empty.")
                else:
                    USER_DB[new_user] = {"password": new_pass, "role": new_role}
                    save_user_db()
                    st.success("Account created! You can now log in.")

def applicant_page():
    st.title("👤 Applicant's Page")
    if "applicant_page" not in st.session_state:
        st.session_state.applicant_page = None
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📤 Resume Upload"):
            st.session_state.applicant_page = "Resume Upload"
    with col2:
        if st.button("🔎 Job Search"):
            st.session_state.applicant_page = "Job Search"
    st.markdown("---")
    if st.session_state.applicant_page == "Resume Upload":
        st.subheader("📤 Upload Your Resume")
        uploaded_files = st.file_uploader("Upload your resume(s)", accept_multiple_files=True, type=["pdf", "doc", "docx"])
        if uploaded_files:
            for uploaded_file in uploaded_files:
                name = save_uploaded_file(uploaded_file)
                st.write(f"✅ Uploaded: `{name}`")
    elif st.session_state.applicant_page == "Job Search":
        st.subheader("🇵🇭 Real-Time Job Search (Philippines)")
        st.sidebar.header("Search Filters")
        search_query = st.sidebar.text_input("Keyword (e.g., developer, nurse)")
        location = st.sidebar.text_input("Location (e.g., Manila, Cebu, Remote)", value="Philippines")
        if search_query:
            st.subheader(f"Results for **{search_query}** in **{location}**")
            jobs = get_jobs(search_query, location)
            if jobs:
                for job in jobs:
                    st.markdown(f"""
                    ### {job['job_title']}
                    **Company:** {job.get('employer_name', 'N/A')}  
                    **Location:** {job.get('job_city', 'N/A')}, {job.get('job_country', '')}  
                    **Posted:** {job.get('job_posted_at_datetime_utc', 'N/A')}  
                    **Description:** {job.get('job_description', '')[:300]}...  
                    [🔗 View Job Posting]({job.get('job_apply_link', '#')})  
                    ---
                    """)
            else:
                st.warning("No jobs found. Try a different keyword or location.")
        else:
            st.info("Use the sidebar to search for jobs.")
    else:
        st.info("Please select an option above.")

def employer_page():
    st.title("🏢 Employer's Page")
    if "employer_page" not in st.session_state:
        st.session_state.employer_page = None
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📁 Resume Pool"):
            st.session_state.employer_page = "Resume Pool"
    with col2:
        if st.button("🎯 Resume Screener"):
            st.session_state.employer_page = "Resume Screener"
    st.markdown("---")
    if st.session_state.employer_page == "Resume Pool":
        st.subheader("📁 Resume Pool")
        resumes = os.listdir(UPLOAD_DIR)
        if resumes:
            for resume in resumes:
                file_path = os.path.join(UPLOAD_DIR, resume)
                with open(file_path, "rb") as f:
                    file_bytes = f.read()
                st.write(f"**📄 {resume}**")
                st.download_button("⬇️ Download", file_bytes, file_name=resume)
                st.markdown("---")
        else:
            st.info("No resumes uploaded yet.")
    elif st.session_state.employer_page == "Resume Screener":
        # Resume screening logic is unchanged (not included here to save space)
        pass
    else:
        st.info("Please select an option above.")

def admin_page():
    st.title("🛠️ Admin Dashboard")
    if "admin_page" not in st.session_state:
        st.session_state.admin_page = None
    cols = st.columns(6)
    labels = [
        "📤 Resume Upload",
        "🔎 Job Search",
        "🎯 Resume Screener",
        "📁 Resume Pool",
        "👥 User Management",
        "📊 Screening Analytics"
    ]
    for i, label in enumerate(labels):
        with cols[i]:
            if st.button(label):
                st.session_state.admin_page = label
    st.markdown("---")
    # Same logic continues...

def main():
    if "logged_in" not in st.session_state or not st.session_state.logged_in:
        login()
    else:
        st.sidebar.title("Navigation")
        role = st.session_state.role

        if role == "Applicant":
            st.sidebar.write(f"Logged in as {st.session_state.username} (Applicant)")
            if st.sidebar.button("Log out"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
            applicant_page()

        elif role == "Employer":
            st.sidebar.write(f"Logged in as {st.session_state.username} (Employer)")
            if st.sidebar.button("Log out"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
            employer_page()

        elif role == "Admin":
            st.sidebar.write(f"Logged in as {st.session_state.username} (Admin)")
            if st.sidebar.button("Log out"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
            admin_page()

if __name__ == "__main__":
    main()
