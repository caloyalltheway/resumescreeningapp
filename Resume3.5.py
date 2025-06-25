import streamlit as st
import re
from pdfminer.high_level import extract_text
import docx
import spacy
from typing import List
from datetime import datetime
import pandas as pd
import os

# --- Page Config & Styling ---
st.set_page_config(
    page_title="🎯 Resume Screener",
    layout="wide",
    page_icon="📝"
)

# Custom CSS
st.markdown(
    """
    <style>
    body { font-family: Arial, sans-serif; background-color: #f9fafc; }
    .stApp { background-color: #f9fafc; }
    h1, h2, h3 { color: #1e3a8a; }
    div[data-testid="stMetricLabel"] { font-weight: bold; color: #1e3a8a; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; color: #2563eb; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Sidebar Input ---
st.sidebar.title("📂 Upload & Job Info")
uploaded_file = st.sidebar.file_uploader(
    "Upload resume (PDF or DOCX)", type=["pdf", "docx"]
)
job_description = st.sidebar.text_area(
    "Job description:", height=200, placeholder="e.g. Python, SQL, project management"
)

# --- NLP model ---
nlp = spacy.load("en_core_web_sm")
EXCEL_DB = "screening_results.xlsx"

# --- Functions ---
def read_pdf(file_path: str) -> str:
    return extract_text(file_path)

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

# ---- Main Processing ----
st.title("🎯 Resume Screening App")

st.markdown(
    "Upload a resume and enter the job description on the left. We'll highlight matched skills and extract contact info."
)

if uploaded_file and job_description.strip():
    temp_file = f"temp_{uploaded_file.name}"
    with open(temp_file, "wb") as f:
        f.write(uploaded_file.getbuffer())
    resume_text = read_pdf(temp_file) if uploaded_file.name.endswith(".pdf") else read_docx(temp_file)

    skills = extract_skills(job_description)
    score = score_resume(resume_text, skills)
    matched_skills = [s for s in skills if re.search(rf"\b{re.escape(s)}\b", resume_text, re.IGNORECASE)]
    email = extract_email(resume_text)
    phone = extract_phone(resume_text)

    st.success(f"✅ Uploaded {uploaded_file.name}")

    # Two-column layout
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("🔍 Contact Info")
        st.write(f"📧 {email}")
        st.write(f"📞 {phone}")

        st.metric(label="Match Score (%)", value=f"{score:.2f}")
        st.write(f"Skills matched: {len(matched_skills)}/{len(skills)}")

    with col2:
        st.subheader("📜 Resume Preview")
        highlighted_resume = highlight_text(resume_text, matched_skills)
        st.markdown(
            f"""
            <div style="
                background:#ffffff;
                padding:1rem;
                border:1px solid #e2e8f0;
                border-radius:0.5rem;
                height:400px;           /* fixed height */
                overflow-y:auto;        /* scroll inside */
                white-space:pre-wrap;
            ">{highlighted_resume}</div>
            """,
            unsafe_allow_html=True,
        )

    # Save to Excel
    new_row = {
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Filename": uploaded_file.name,
        "Email": email,
        "Contact_Number": phone,
        "Match_Score(%)": round(score, 2),
        "Matched_Skills": ", ".join(matched_skills),
        "Total_Skills": len(skills),
        "Matched_Skills_Count": len(matched_skills),
    }

    if os.path.exists(EXCEL_DB):
        df = pd.read_excel(EXCEL_DB)
        if "Email" not in df.columns:
            df["Email"] = ""
        if "Contact_Number" not in df.columns:
            df["Contact_Number"] = ""
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    else:
        df = pd.DataFrame([new_row])
    df.to_excel(EXCEL_DB, index=False)
    st.success(f"✅ Saved this screening to `{EXCEL_DB}`!")

# ---- Past Records ----
st.markdown("---")
st.header("📂 Past Screening Records")
if os.path.exists(EXCEL_DB):
    df = pd.read_excel(EXCEL_DB)
    st.dataframe(df)
else:
    st.info("No screenings logged yet. Upload a resume and job description to begin!")

