from app.models.schemas import JobRequirement, CandidateCV, ScreeningResult


def generate_missing_skill_questions(missing_skills: list[str]) -> list[str]:
    """
    Génère une question pour chaque compétence obligatoire manquante.
    """
    questions = []

    for skill in missing_skills:
        questions.append(
            f"Vous n’avez pas mentionné la compétence '{skill}' dans votre CV. "
            f"Avez-vous déjà travaillé avec cette technologie ou une technologie similaire ?"
        )

    return questions


def generate_language_questions(job: JobRequirement, candidate: CandidateCV) -> list[str]:
    """
    Génère des questions pour les langues requises non détectées.
    """
    questions = []

    candidate_languages = [lang.lower() for lang in candidate.languages]
    required_languages = [lang.lower() for lang in job.required_languages]

    missing_languages = [lang for lang in required_languages if lang not in candidate_languages]

    for lang in missing_languages:
        questions.append(
            f"Le poste demande la langue '{lang}'. Pouvez-vous préciser votre niveau dans cette langue ?"
        )

    return questions


def generate_experience_question(job: JobRequirement, candidate: CandidateCV) -> list[str]:
    """
    Génère une question si l'expérience détectée est inférieure au minimum demandé.
    """
    if candidate.experience_years < job.minimum_experience_years:
        return [
            f"Le poste demande au moins {job.minimum_experience_years} an(s) d'expérience. "
            f"Pouvez-vous détailler les projets, stages ou missions les plus proches de ce poste ?"
        ]
    return []


def generate_degree_question(job: JobRequirement, screening: ScreeningResult) -> list[str]:
    """
    Génère une question si le diplôme semble insuffisant ou non détecté.
    """
    for weakness in screening.weaknesses:
        if "Diplôme insuffisant" in weakness or "non détecté" in weakness:
            return [
                f"Le poste demande au minimum le niveau '{job.minimum_degree}'. "
                f"Pouvez-vous préciser votre diplôme exact ou votre niveau d’études actuel ?"
            ]
    return []


def generate_general_hr_questions(job: JobRequirement) -> list[str]:
    """
    Génère quelques questions RH génériques utiles pour la présélection.
    """
    questions = [
        "Êtes-vous disponible actuellement pour commencer ce poste ?",
        f"Êtes-vous intéressé(e) par un poste de type '{job.employment_type}' ?" if job.employment_type else "Quel type de contrat recherchez-vous ?",
        f"Pouvez-vous travailler à {job.location} ?" if job.location else "Êtes-vous mobile géographiquement ?"
    ]
    return questions


def generate_chatbot_questions(
    job: JobRequirement,
    candidate: CandidateCV,
    screening: ScreeningResult
) -> list[str]:
    """
    Fonction principale :
    génère une liste finale de questions adaptées au candidat.
    """
    questions = []

    # 1. compétences obligatoires manquantes
    questions.extend(generate_missing_skill_questions(screening.missing_required_skills))

    # 2. langues non détectées
    questions.extend(generate_language_questions(job, candidate))

    # 3. expérience
    questions.extend(generate_experience_question(job, candidate))

    # 4. diplôme
    questions.extend(generate_degree_question(job, screening))

    # 5. questions RH générales
    questions.extend(generate_general_hr_questions(job))

    # éviter doublons éventuels tout en gardant l'ordre
    unique_questions = []
    seen = set()

    for q in questions:
        if q not in seen:
            unique_questions.append(q)
            seen.add(q)

    return unique_questions