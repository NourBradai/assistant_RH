import uuid
from app.models.schemas import JobRequirement, CandidateCV, ScreeningResult, ChatQuestion


PRIORITY_ORDER = {
    "high": 3,
    "medium": 2,
    "low": 1
}


def normalize_list(values: list[str]) -> list[str]:
    """
    Met une liste en minuscules, supprime les espaces inutiles
    et enlève les doublons.
    """
    return list({v.strip().lower() for v in values if v and v.strip()})


def create_skill_question(skill: str) -> ChatQuestion:
    """
    Crée une question ciblée pour une compétence obligatoire manquante.
    """
    return ChatQuestion(
        question_id=str(uuid.uuid4()),
        question_type="skill",
        question_text=f"Avez-vous déjà utilisé {skill} ou une technologie similaire dans un projet concret ?",
        objective=f"Vérifier si le candidat possède une expérience directe ou transférable en {skill}.",
        expected_signals=[
            skill.lower(),
            "project",
            "projet",
            "stage",
            "mission",
            "api",
            "backend",
            "developed",
            "développé"
        ],
        weight=1.5,
        priority="high"
    )


def create_language_question(language: str) -> ChatQuestion:
    """
    Crée une question pour vérifier un niveau de langue requis.
    """
    return ChatQuestion(
        question_id=str(uuid.uuid4()),
        question_type="language",
        question_text=f"Pouvez-vous préciser votre niveau en {language} et dans quel contexte vous l'utilisez ?",
        objective=f"Vérifier le niveau réel du candidat en {language}.",
        expected_signals=[
            language.lower(),
            "a1", "a2", "b1", "b2", "c1", "c2",
            "beginner", "intermediate", "advanced",
            "débutant", "intermédiaire", "avancé",
            "courant", "fluent", "professional", "professionnel",
            "documentation", "meeting", "communication"
        ],
        weight=1.2,
        priority="medium"
    )


def create_experience_question(min_years: float) -> ChatQuestion:
    """
    Crée une question lorsque l'expérience détectée semble insuffisante.
    """
    return ChatQuestion(
        question_id=str(uuid.uuid4()),
        question_type="experience",
        question_text=(
            f"Le poste demande environ {min_years} an(s) d'expérience. "
            f"Pouvez-vous détailler les projets, stages ou missions les plus proches de ce poste ?"
        ),
        objective="Vérifier si le candidat possède une expérience concrète pertinente malgré un score initial faible sur l'expérience.",
        expected_signals=[
            "project", "projet",
            "stage", "internship",
            "mission", "client",
            "backend", "api", "development",
            "developed", "implemented", "réalisé", "développé"
        ],
        weight=1.4,
        priority="high"
    )


def create_degree_question(min_degree: str) -> ChatQuestion:
    """
    Crée une question pour confirmer le niveau d'études.
    """
    return ChatQuestion(
        question_id=str(uuid.uuid4()),
        question_type="degree",
        question_text=f"Pouvez-vous préciser votre diplôme exact et votre niveau d’études actuel ?",
        objective=f"Vérifier si le candidat satisfait au minimum académique attendu ({min_degree}).",
        expected_signals=[
            "bac", "bachelor", "licence",
            "master", "m1", "m2",
            "ingénieur", "engineer",
            "doctorat", "phd",
            min_degree.lower()
        ],
        weight=1.1,
        priority="medium"
    )


def create_availability_question() -> ChatQuestion:
    """
    Crée une question RH sur la disponibilité.
    """
    return ChatQuestion(
        question_id=str(uuid.uuid4()),
        question_type="hr",
        question_text="Êtes-vous disponible actuellement pour commencer ce poste ?",
        objective="Vérifier la disponibilité du candidat.",
        expected_signals=[
            "oui", "yes",
            "immédiatement", "immediately",
            "disponible", "available",
            "préavis", "notice"
        ],
        weight=0.8,
        priority="low"
    )


def create_location_question(location: str) -> ChatQuestion:
    """
    Crée une question RH sur la mobilité / localisation.
    """
    return ChatQuestion(
        question_id=str(uuid.uuid4()),
        question_type="hr",
        question_text=f"Pouvez-vous travailler à {location} ou dans cette zone géographique ?",
        objective="Vérifier la mobilité géographique du candidat.",
        expected_signals=[
            "oui", "yes",
            "mobile", "mobilité",
            "remote", "hybrid", "hybride",
            location.lower()
        ],
        weight=0.7,
        priority="low"
    )


def create_contract_question(employment_type: str) -> ChatQuestion:
    """
    Crée une question RH sur le type de contrat / format du poste.
    """
    return ChatQuestion(
        question_id=str(uuid.uuid4()),
        question_type="hr",
        question_text=f"Êtes-vous intéressé(e) par un poste de type '{employment_type}' ?",
        objective="Vérifier l'adéquation entre le poste proposé et les attentes du candidat.",
        expected_signals=[
            "oui", "yes",
            "intéressé", "interested",
            employment_type.lower()
        ],
        weight=0.7,
        priority="low"
    )


def generate_skill_questions(screening: ScreeningResult) -> list[ChatQuestion]:
    """
    Génère des questions pour chaque compétence obligatoire manquante.
    """
    questions = []
    for skill in screening.missing_required_skills:
        questions.append(create_skill_question(skill))
    return questions


def generate_language_questions(job: JobRequirement, candidate: CandidateCV) -> list[ChatQuestion]:
    """
    Génère des questions pour les langues requises absentes du profil candidat.
    """
    questions = []
    required_languages = normalize_list(job.required_languages)
    candidate_languages = normalize_list(candidate.languages)

    missing_languages = [lang for lang in required_languages if lang not in candidate_languages]

    for language in missing_languages:
        questions.append(create_language_question(language))

    return questions


def generate_experience_questions(job: JobRequirement, candidate: CandidateCV) -> list[ChatQuestion]:
    """
    Génère une question si l'expérience du candidat semble inférieure au minimum demandé.
    """
    if candidate.experience_years < job.minimum_experience_years:
        return [create_experience_question(job.minimum_experience_years)]
    return []


def generate_degree_questions(job: JobRequirement, screening: ScreeningResult) -> list[ChatQuestion]:
    """
    Génère une question si le diplôme est insuffisant ou non détecté.
    """
    for weakness in screening.weaknesses:
        weakness_lower = weakness.lower()
        if "diplôme insuffisant" in weakness_lower or "non détecté" in weakness_lower:
            if job.minimum_degree:
                return [create_degree_question(job.minimum_degree)]
    return []


def generate_hr_questions(job: JobRequirement) -> list[ChatQuestion]:
    """
    Génère des questions RH simples.
    """
    questions = [create_availability_question()]

    if job.location:
        questions.append(create_location_question(job.location))

    if job.employment_type:
        questions.append(create_contract_question(job.employment_type))

    return questions


def sort_questions_by_priority_and_weight(questions: list[ChatQuestion]) -> list[ChatQuestion]:
    """
    Trie les questions :
    1. par priorité
    2. puis par poids
    """
    return sorted(
        questions,
        key=lambda q: (PRIORITY_ORDER.get(q.priority, 0), q.weight),
        reverse=True
    )


def build_interview_plan(
    job: JobRequirement,
    candidate: CandidateCV,
    screening: ScreeningResult,
    max_questions: int = 6
) -> list[ChatQuestion]:
    """
    Fonction principale.
    Construit un plan d'entretien ciblé à partir du screening initial.
    """
    questions = []

    questions.extend(generate_skill_questions(screening))
    questions.extend(generate_language_questions(job, candidate))
    questions.extend(generate_experience_questions(job, candidate))
    questions.extend(generate_degree_questions(job, screening))
    questions.extend(generate_hr_questions(job))

    questions = sort_questions_by_priority_and_weight(questions)

    return questions[:max_questions] 