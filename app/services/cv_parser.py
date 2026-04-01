"""
Service d'extraction et d'analyse de CVs au format PDF.
Utilise PyMuPDF pour l'extraction de texte et des expressions régulières pour la structuration des données.
"""
import re
import uuid
import datetime
import fitz

from app.models.schemas import CandidateCV
from app.utils.text_cleaner import clean_text

# --- CONFIGURATION DES LOGIQUES MÉTIER ---

# Hiérarchie des diplômes pour l'extraction (nom -> importance)
DEGREE_HIERARCHY = {
    "doctorat": 5, "phd": 5,
    "master": 4, "ingénieur": 4, "engineer": 4, "m2": 4,
    "licence": 3, "bachelor": 3, "m1": 3, "l3": 3,
    "bts": 2, "dut": 2, "deust": 2,
    "bac": 1
}

# Cartographie des compétences (Normalisation)
SKILL_MAP = {
    "Python": [r"python\d?"],
    "Java": [r"java(?!\s*script)"],
    "JavaScript": [r"javascript", r"js", r"es6"],
    "TypeScript": [r"typescript", r"ts"],
    "React": [r"react", r"react\.js", r"reactjs"],
    "Angular": [r"angular", r"angularjs"],
    "Vue.js": [r"vue", r"vuejs", r"vue\.js"],
    "Node.js": [r"node", r"nodejs", r"node\.js"],
    "FastAPI": [r"fastapi"],
    "Django": [r"django"],
    "Flask": [r"flask"],
    "SQL": [r"sql", r"mysql", r"postgresql", r"postgres", r"oracle"],
    "MongoDB": [r"mongodb", r"mongo"],
    "Docker": [r"docker"],
    "Kubernetes": [r"kubernetes", r"k8s"],
    "AWS": [r"aws", r"amazon web services"],
    "Azure": [r"azure"],
    "GCP": [r"gcp", r"google cloud"],
    "DevOps": [r"devops", r"ci/cd", r"git", r"github", r"gitlab"],
    "Machine Learning": [r"machine learning", r"ml", r"deep learning", r"nlp"],
    "Data Science": [r"data science", r"pandas", r"numpy", r"scikit-learn"]
}

LANGUAGES = ["français", "french", "anglais", "english", "arabe", "arabic", "espagnol", "spanish", "allemand", "german"]

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extrait le texte brut d'un flux binaire PDF.
    """
    text = ""
    pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
    for page in pdf_document:
        text += page.get_text() + "\n"
    pdf_document.close()
    return clean_text(text)

def extract_email(text: str) -> str | None:
    """
    Utilise une regex pour trouver l'adresse email du candidat.
    """
    match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    return match.group(0) if match else None

def extract_phone(text: str) -> str | None:
    """
    Cherche un pattern de numéro de téléphone.
    """
    match = re.search(r"(\+?\d[\d\s\.\-]{8,}\d)", text)
    return match.group(0).strip() if match else None

def extract_skills(text: str) -> list[str]:
    """
    Extrait et normalise les compétences.
    """
    found_skills = set()
    text_lower = text.lower()
    for skill_name, patterns in SKILL_MAP.items():
        for pattern in patterns:
            if re.search(r"\b" + pattern + r"\b", text_lower):
                found_skills.add(skill_name)
                break
    return sorted(list(found_skills))

def extract_degree(text: str) -> str | None:
    """
    Détermine le niveau d'éducation le plus élevé. 
    Retourne le nom capitalisé pour correspondre au DEGREE_RANK du matcher.
    """
    text_lower = text.lower()
    best_degree = None
    max_score = -1
    for degree, score in DEGREE_HIERARCHY.items():
        if re.search(r"\b" + re.escape(degree) + r"\b", text_lower):
            if score > max_score:
                max_score = score
                best_degree = degree.capitalize()
    return best_degree

def estimate_experience_years(text: str) -> float:
    """
    Calcule l'expérience pro en fusionnant les intervalles de dates.
    Exclut les sections ou lignes liées à la formation.
    """
    current_year = datetime.datetime.now().year
    exp_headers = [r"expérience", r"experience", r"parcours professionnel", r"emplois", r"missions"]
    edu_headers = [r"formation", r"éducation", r"education", r"études", r"cursus", r"diplômes"]
    
    lines = text.split('\n')
    experience_text = ""
    in_exp = False
    for line in lines:
        l_low = line.lower().strip()
        if not l_low: continue
        if any(re.search(r"\b" + h + r"\b", l_low) for h in exp_headers):
            in_exp = True
            continue
        if any(re.search(r"\b" + h + r"\b", l_low) for h in edu_headers):
            in_exp = False
            continue
        if in_exp:
            if not any(re.search(r"\b" + d + r"\b", l_low) for d in DEGREE_HIERARCHY.keys()):
                experience_text += line + "\n"
    
    source_text = experience_text if experience_text.strip() else text
    patterns = re.findall(r"(\d{4})\s*[\-–—]\s*(\d{4}|présent|present|aujourd'hui|today|now)", source_text.lower())
    
    if not patterns:
        years = re.findall(r"\b(20\d{2}|19\d{2})\b", source_text)
        if len(years) < 2: return 0.0
        unique_years = sorted(list(set([int(y) for y in years])))
        return float(min(current_year - unique_years[0], unique_years[-1] - unique_years[0]))

    # Fusion d'intervalles (Merge Intervals) para éviter les doublons (CDI + Freelance)
    ranges = []
    for start, end in patterns:
        s_yr = int(start)
        e_yr = current_year if end in ["présent", "present", "aujourd'hui", "today", "now"] else int(end)
        if e_yr >= s_yr: ranges.append([s_yr, e_yr])
    
    if not ranges: return 0.0
    ranges.sort()
    merged = [ranges[0]]
    for cur in ranges[1:]:
        prev = merged[-1]
        if cur[0] <= prev[1]: prev[1] = max(prev[1], cur[1])
        else: merged.append(cur)
    
    return round(float(sum(e - s for s, e in merged)), 1)

def extract_name(text: str, email: str | None = None) -> str:
    """
    Tente de trouver le nom du candidat.
    Heuristique : regarde les 5 premières lignes et ignore les lignes de contact.
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines: return "Unknown Candidate"
    for line in lines[:5]:
        if len(line.split()) <= 4 and not re.search(r"(@|\d{5,}|http)", line):
            return line
    if email: return email.split("@")[0].replace(".", " ").title()
    return "Unknown Candidate"

def parse_cv_pdf(file_bytes: bytes, filename: str = "cv.pdf") -> CandidateCV:
    """
    Fonction orchestratrice : PDF -> CandidateCV structuré.
    """
    raw_text = extract_text_from_pdf(file_bytes)
    email = extract_email(raw_text)
    candidate = CandidateCV(
        candidate_id=str(uuid.uuid4()),
        name=extract_name(raw_text, email),
        email=email,
        phone=extract_phone(raw_text),
        skills=extract_skills(raw_text),
        degree=extract_degree(raw_text),
        experience_years=estimate_experience_years(raw_text),
        languages=[l for l in LANGUAGES if l in raw_text.lower()],
        certifications=[],
        projects=[],
        raw_text=raw_text
    )
    return candidate