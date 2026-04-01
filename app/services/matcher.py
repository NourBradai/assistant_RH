from app.models.schemas import JobRequirement, CandidateCV, ScreeningResult

# Même logique de hiérarchie que dans le parser
DEGREE_RANK = {
    "Bac": 1,
    "Bts": 2,
    "Dut": 2,
    "Deust": 2,
    "Licence": 3,
    "Bachelor": 3,
    "M1": 3,
    "L3": 3,
    "Master": 4,
    "Ingénieur": 4,
    "Engineer": 4,
    "M2": 4,
    "Doctorat": 5,
    "Phd": 5
}


def normalize_list(values: list[str]) -> list[str]:
    """
    Met une liste en minuscules et supprime les doublons.
    Sert à comparer proprement les chaînes sans problème de casse.
    """
    return list({v.strip().lower() for v in values if v and v.strip()})


def match_required_skills(job: JobRequirement, candidate: CandidateCV) -> tuple[list[str], list[str]]:
    """
    Retourne :
    - les compétences obligatoires trouvées
    - les compétences obligatoires manquantes
    """
    job_required = normalize_list(job.required_skills)
    candidate_skills = normalize_list(candidate.skills)

    matched = [skill for skill in job_required if skill in candidate_skills]
    missing = [skill for skill in job_required if skill not in candidate_skills]

    return matched, missing


def match_preferred_skills(job: JobRequirement, candidate: CandidateCV) -> list[str]:
    """
    Retourne les compétences bonus trouvées.
    """
    job_preferred = normalize_list(job.preferred_skills)
    candidate_skills = normalize_list(candidate.skills)

    matched = [skill for skill in job_preferred if skill in candidate_skills]
    return matched


def language_match_score(job: JobRequirement, candidate: CandidateCV) -> tuple[list[str], float]:
    """
    Compare les langues requises.
    Retourne :
    - les langues trouvées
    - le score partiel langue
    """
    required_languages = normalize_list(job.required_languages)
    candidate_languages = normalize_list(candidate.languages)

    if not required_languages:
        return [], 0.0

    matched_languages = [lang for lang in required_languages if lang in candidate_languages]
    ratio = len(matched_languages) / len(required_languages)

    return matched_languages, ratio


def degree_is_valid(candidate_degree: str | None, minimum_degree: str | None) -> bool:
    """
    Vérifie si le diplôme du candidat satisfait le minimum demandé.
    Utilise une recherche par sous-chaîne pour être plus flexible (ex: 'Master en Informatique').
    """
    if not minimum_degree:
        return True

    if not candidate_degree:
        return False

    # On cherche le rang le plus élevé parmi les mots-clés trouvés dans le diplôme du candidat
    candidate_rank = 0
    for deg, rank in DEGREE_RANK.items():
        if deg.lower() in candidate_degree.lower():
            candidate_rank = max(candidate_rank, rank)

    # On cherche le rang requis par rapport au job
    required_rank = 0
    for deg, rank in DEGREE_RANK.items():
        if deg.lower() in minimum_degree.lower():
            required_rank = max(required_rank, rank)

    return candidate_rank >= required_rank


def experience_score(candidate_years: float, minimum_years: float) -> float:
    """
    Retourne un ratio entre 0 et 1 pour mesurer si l'expérience est suffisante.
    """
    if minimum_years <= 0:
        return 1.0

    ratio = candidate_years / minimum_years
    return min(ratio, 1.0)


def build_strengths(matched_required: list[str], matched_preferred: list[str], degree_ok: bool, experience_ok: bool) -> list[str]:
    """
    Construit une liste simple de points forts.
    """
    strengths = []

    if matched_required:
        strengths.append(f"{len(matched_required)} compétence(s) obligatoire(s) validée(s)")

    if matched_preferred:
        strengths.append(f"{len(matched_preferred)} compétence(s) bonus trouvée(s)")

    if degree_ok:
        strengths.append("Diplôme compatible avec le poste")

    if experience_ok:
        strengths.append("Expérience suffisante")

    return strengths


def build_weaknesses(missing_required: list[str], degree_ok: bool, experience_ok: bool, matched_languages: list[str], job: JobRequirement) -> list[str]:
    """
    Construit une liste simple de points faibles.
    """
    weaknesses = []

    if missing_required:
        weaknesses.append("Compétences obligatoires manquantes : " + ", ".join(missing_required))

    if not degree_ok:
        weaknesses.append("Diplôme insuffisant ou non détecté")

    if not experience_ok:
        weaknesses.append("Expérience inférieure au minimum demandé")

    if job.required_languages and len(matched_languages) < len(job.required_languages):
        weaknesses.append("Certaines langues requises sont absentes")

    return weaknesses


def compute_screening_result(job: JobRequirement, candidate: CandidateCV) -> ScreeningResult:
    """
    Fonction principale de matching/scoring.
    Compare un candidat à une offre et retourne un ScreeningResult.
    """
    matched_required, missing_required = match_required_skills(job, candidate)
    matched_preferred = match_preferred_skills(job, candidate)
    matched_languages, language_ratio = language_match_score(job, candidate)

    degree_ok = degree_is_valid(candidate.degree, job.minimum_degree)
    exp_ratio = experience_score(candidate.experience_years, job.minimum_experience_years)
    experience_ok = exp_ratio >= 1.0

    score = 0.0

    # 1. compétences obligatoires
    if job.required_skills:
        required_ratio = len(matched_required) / len(job.required_skills)
        score += required_ratio * job.weights.required_skills

    # 2. compétences bonus
    if job.preferred_skills:
        preferred_ratio = len(matched_preferred) / len(job.preferred_skills)
        score += preferred_ratio * job.weights.preferred_skills

    # 3. expérience
    score += exp_ratio * job.weights.experience

    # 4. diplôme
    if degree_ok:
        score += job.weights.degree

    # 5. langues
    score += language_ratio * job.weights.languages

    # 6. certifications / projets
    extra_points = 0.0
    if candidate.certifications or candidate.projects:
        extra_points = job.weights.projects_certifications
    score += extra_points

    strengths = build_strengths(matched_required, matched_preferred, degree_ok, experience_ok)
    weaknesses = build_weaknesses(missing_required, degree_ok, experience_ok, matched_languages, job)

    if len(missing_required) > 0:
        status = "review"
    elif score >= 75:
        status = "shortlisted"
    elif score >= 50:
        status = "review"
    else:
        status = "rejected"

    return ScreeningResult(
        candidate_id=candidate.candidate_id,
        job_id=job.job_id,
        initial_score=round(score, 2),
        matched_required_skills=matched_required,
        missing_required_skills=missing_required,
        matched_preferred_skills=matched_preferred,
        strengths=strengths,
        weaknesses=weaknesses,
        status=status
    )