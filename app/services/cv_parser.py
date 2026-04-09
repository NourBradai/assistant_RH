"""
Service d'extraction et d'analyse de CVs au format PDF.
Utilise PyMuPDF pour l'extraction de texte et des expressions régulières pour la structuration des données.
"""
import re
import uuid
import datetime
import fitz
import nltk
try:
    from nltk.corpus import stopwords
except ImportError:
    pass
from typing import Dict, List, Optional

from app.models.schemas import CandidateCV, CandidateEvidenceItem, ParsedCandidateProfile
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

def extract_skills_from_map(text: str) -> set:
    """
    Phase 1 : Extraction via la SKILL_MAP (normalisée).
    Cherche les patterns prédéfinis n'importe où dans le texte.
    """
    found = set()
    text_lower = text.lower()
    for skill_name, patterns in SKILL_MAP.items():
        for pattern in patterns:
            if re.search(r"\b" + pattern + r"\b", text_lower):
                found.add(skill_name)
                break
    return found


def extract_free_skills(text: str) -> set:
    """
    Phase 2 : Extraction libre des compétences techniques non couverte par SKILL_MAP.
    """
    found = set()

    # Préparation des stopwords linguistiques (NLTK)
    try:
        fr_stops = set(stopwords.words('french'))
        en_stops = set(stopwords.words('english'))
    except LookupError:
        nltk.download('stopwords', quiet=True)
        fr_stops = set(stopwords.words('french'))
        en_stops = set(stopwords.words('english'))

    # Mots parasites métier non couverts par NLTK (contextuel HR/Tech)
    DOMAIN_EXCLUDE = {
        "junior", "senior", "lead", "stage", "projet", "mission", "expérience",
        "compétences", "skills", "outils", "technologies", "connaissance", "maîtrise",
        "utilisation", "développement", "conception", "réalisation", "mise", "en", "œuvre",
        "linkedin", "email", "téléphone", "phone", "adresse", "address"
    }

    # Nettoyage IA avancé : spaCy NER (Named Entity Recognition)
    spacy_excludes = set()
    try:
        import spacy
        nlp = spacy.load("fr_core_news_sm")
        doc = nlp(text)
        # On exclut Lieux (LOC, GPE), Dates (DATE, TIME) et Noms Propres (PERSON)
        # Attention: On ne filtre SURTOUT PAS "ORG" ou "PRODUCT" qui pourraient correspondre à des technos !
        for ent in doc.ents:
            if ent.label_ in ["LOC", "GPE", "DATE", "TIME", "PERSON"]:
                # Ex: "janvier", "2023", "Paris", "France"
                for word in ent.text.split():
                    spacy_excludes.add(word.lower().strip("(),.;/"))
    except (ImportError, Exception):
        pass # Fallback silencieux si spaCy n'est pas encore installé

    EXCLUDE = fr_stops | en_stops | DOMAIN_EXCLUDE | spacy_excludes

    # On cible les lignes candidates = listes séparées ou tokens courts
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped: continue
        
        # On ignore les phrases trop longues (probablement du texte narratif)
        if len(stripped.split()) > 15: continue
        
        # Séparation par de nombreux délimiteurs
        tokens = re.split(r"[,;/|•·▪▸\-–—\n\t:]+", stripped)
        for token in tokens:
            token = token.strip().strip("()[].*")
            
            # Filtre heuristique : 
            # - Longueur raisonnable
            # - Pas que des chiffres
            # - Pas un lien URL
            # - Pas dans la blacklist
            if (
                2 <= len(token) <= 25
                and re.search(r"[A-Za-z]", token)
                and not re.search(r"(http|www|\.com|\.fr|\.net)", token.lower())
                and token.lower() not in EXCLUDE
            ):
                # On évite les tokens qui sont des phrases entières
                if len(token.split()) <= 3:
                    found.add(token)

    # Supprimer les tokens qui sont déjà couverts par la SKILL_MAP
    map_values_lower = {v.lower() for v in SKILL_MAP.keys()}
    found = {s for s in found if s.lower() not in map_values_lower}

    return found


def extract_skills(text: str) -> list[str]:
    """
    Extraction hybride des compétences.
    Phase 1 : SKILL_MAP (normalisée, dédupliquée)
    Phase 2 : Extraction libre (tokens techniques orphelins)
    """
    normalized = extract_skills_from_map(text)     # ex: {"Python", "Docker"}
    free_form  = extract_free_skills(text)          # ex: {"Spring Boot", "Kafka", "Terraform"}

    all_skills = normalized | free_form
    return sorted(list(all_skills))


def extract_degree(text: str) -> str | None:
    """
    Détermine le niveau d'éducation le plus élevé.
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
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines: return "Unknown Candidate"
    for line in lines[:5]:
        if len(line.split()) <= 4 and not re.search(r"(@|\d{5,}|http)", line):
            return line
    if email: return email.split("@")[0].replace(".", " ").title()
    return "Unknown Candidate"

def extract_sections(text: str) -> Dict[str, str]:
    """
    Découpe le texte du CV en sections via des expressions régulières robustes.
    """
    sections = {
        "summary": "",
        "experience": "",
        "education": "",
        "projects": "",
        "skills": "",
        "certifications": "",
        "other": ""
    }
    
    headers = {
        "experience": [r"expérience", r"experience", r"parcours professionnel", r"emplois", r"missions", r"historique"],
        "education": [r"formation", r"éducation", r"education", r"études", r"cursus", r"diplômes", r"académique"],
        "projects": [r"projets", r"projects", r"réalisations", r"achievements"],
        "skills": [r"compétences", r"skills", r"aptitudes", r"outils", r"technologies"],
        "certifications": [r"certifications", r"certificats", r"acquisitions"],
        "summary": [r"résumé", r"profil", r"summary", r"objectif", r"introduction"]
    }
    
    lines = text.split("\n")
    current_section = "summary"
    
    for line in lines:
        l_low = line.lower().strip()
        if not l_low: continue
        
        # Détection de header : 
        # On cherche si la ligne commence par un mot-clé de header.
        # On autorise jusqu'à 12 mots pour supporter "Section : Titre du poste"
        found_header = False
        for sec, patterns in headers.items():
            for p in patterns:
                # On cherche le mot-clé au début de la ligne, suivi d'un séparateur ou d'un mot.
                # Regex : début de ligne, optionnel chiffre/puce, puis le mot-clé, 
                # puis soit fin, soit colon, soit espace (début du titre de section).
                header_regex = r"^\s*(?:\d?\.?\s*|[•·▪▸\-\s]*)" + p + r"s?\s*(?::|$|\s)"
                if re.search(header_regex, l_low) and len(l_low.split()) <= 12:
                    current_section = sec
                    found_header = True
                    break
            if found_header: break
        
        # Cas spécial pour les langues qui sont souvent une section à part entière 
        # mais qu'on peut ranger dans 'skills' ou 'other'
        if not found_header and re.search(r"^\s*langues?\s*(:|$|\s)", l_low) and len(l_low.split()) <= 4:
            current_section = "skills" # On range les langues dans skills pour le matching
            found_header = True
        
        if not found_header:
            sections[current_section] += line + "\n"
            
    return sections

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

def parse_cv_to_structured_profile(file_bytes: bytes, filename: str = "cv.pdf") -> ParsedCandidateProfile:
    """
    Version améliorée de l'extraction : produit un profil structuré avec preuves par section.
    """
    cv_info = parse_cv_pdf(file_bytes, filename)
    sections = extract_sections(cv_info.raw_text)
    
    evidence = []
    for section_name, content in sections.items():
        if len(content.strip()) > 20:
            norm_entities = extract_skills(content)
            evidence.append(CandidateEvidenceItem(
                evidence_id=f"ev_{uuid.uuid4().hex[:6]}",
                source_section=section_name,
                original_text=content.strip(),
                normalized_entities=norm_entities,
                confidence_score=0.9 if section_name in ["experience", "projects"] else 0.7
            ))
            
    return ParsedCandidateProfile(
        candidate_id=cv_info.candidate_id,
        cv_info=cv_info,
        evidence=evidence,
        sections=sections
    )