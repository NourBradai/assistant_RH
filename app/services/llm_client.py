import json
import os
from typing import Any

import httpx

from app.models.schemas import (
    ChatQuestion,
    QuestionAnalysis,
    JobRequirement,
    CandidateCV,
)


def get_llm_settings() -> dict[str, str]:
    """
    Récupère la configuration du LLM depuis les variables d'environnement.
    """
    return {
        "mode": os.getenv("LLM_MODE", "mock"),
        "api_url": os.getenv("LLM_API_URL", "").strip(),
        "api_key": os.getenv("LLM_API_KEY", "").strip(),
        "model": os.getenv("LLM_MODEL", "gpt-4o-mini").strip(),
    }


def llm_is_configured() -> bool:
    """
    Vérifie si le mode LLM distant est réellement utilisable.
    """
    settings = get_llm_settings()
    return (
        settings["mode"] == "openai_compatible"
        and bool(settings["api_url"])
        and bool(settings["api_key"])
        and bool(settings["model"])
    )


def build_question_generation_prompt(
    question: ChatQuestion,
    job: JobRequirement,
    candidate: CandidateCV,
) -> str:
    """
    Construit le prompt de génération de question.
    """
    return f"""
Tu es un assistant de présélection RH.

Ta tâche :
reformuler UNE seule question de manière naturelle, professionnelle, claire et courte.

Règles :
- Ne mentionne pas de listes de compétences obligatoires ou d'années d'expérience de manière brute.
- Ta question doit ressembler à une interaction humaine réelle (ex: "Compte tenu de votre parcours en..., qu'en est-il de...").
- Ne commence pas par des introductions comme "En tant qu'assistant..." ou "Ma question est...".
- Réponds UNIQUEMENT par la question.

Contexte du poste :
- Titre : {job.title}
- Compétences obligatoires : {job.required_skills}
- Compétences souhaitées : {job.preferred_skills}
- Diplôme minimum : {job.minimum_degree}
- Expérience minimum : {job.minimum_experience_years}
- Langues requises : {job.required_languages}
- Localisation : {job.location}
- Type d'emploi : {job.employment_type}

Contexte du candidat :
- Nom : {candidate.name}
- Compétences détectées : {candidate.skills}
- Diplôme détecté : {candidate.degree}
- Expérience détectée : {candidate.experience_years}
- Langues détectées : {candidate.languages}

Question interne actuelle :
- Type : {question.question_type}
- Texte de base : {question.question_text}
- Objectif : {question.objective}
- Signaux attendus : {question.expected_signals}

Produis maintenant la meilleure reformulation possible.
""".strip()


def build_answer_analysis_prompt(
    question: ChatQuestion,
    answer_text: str,
    job: JobRequirement,
    candidate: CandidateCV,
) -> str:
    """
    Construit le prompt d'analyse d'une réponse.
    Le LLM doit répondre en JSON strict.
    """
    return f"""
Tu es un assistant d'analyse de réponses dans un chatbot de présélection RH.

Ta tâche :
analyser la réponse du candidat à UNE question précise.

Important :
- Tu dois répondre uniquement en JSON valide.
- Aucune phrase avant ou après le JSON.
- Tous les scores doivent être entre 0 et 100.
- Tu dois être strict, cohérent et factuel.
- Si la réponse est vague, note-la faiblement.
- Si la réponse contient des preuves concrètes, valorise-la.
- Évalue la réponse selon 4 dimensions :
  1. relevance_score
  2. evidence_score
  3. clarity_score
  4. stance_score

Définitions :
- relevance_score : la réponse traite-t-elle vraiment le sujet de la question ?
- evidence_score : y a-t-il une preuve concrète (projet, stage, mission, exemple réel, contexte technique) ?
- clarity_score : la réponse est-elle claire, précise, exploitable ?
- stance_score : la réponse est-elle affirmative, négative, partielle ou hésitante ?

Calcule aussi :
- final_answer_score selon cette formule :
  0.35 * relevance_score
  + 0.30 * evidence_score
  + 0.20 * clarity_score
  + 0.15 * stance_score

Ajoute aussi :
- justification : une phrase courte expliquant le score

Contexte du poste :
- Titre : {job.title}
- Compétences obligatoires : {job.required_skills}
- Expérience minimum : {job.minimum_experience_years}
- Diplôme minimum : {job.minimum_degree}
- Langues requises : {job.required_languages}

Contexte du candidat :
- Nom : {candidate.name}
- Compétences détectées : {candidate.skills}
- Diplôme détecté : {candidate.degree}
- Expérience détectée : {candidate.experience_years}
- Langues détectées : {candidate.languages}

Question :
- Type : {question.question_type}
- Texte : {question.question_text}
- Objectif : {question.objective}
- Signaux attendus : {question.expected_signals}

Réponse du candidat :
{answer_text}

Réponds exactement sous cette forme JSON :
{{
  "relevance_score": 0,
  "evidence_score": 0,
  "clarity_score": 0,
  "stance_score": 0,
  "final_answer_score": 0,
  "justification": ""
}}
""".strip()


def call_openai_compatible_api(prompt: str) -> str:
    """
    Appelle une API compatible OpenAI Chat Completions.
    Retourne le texte brut du message généré.
    """
    settings = get_llm_settings()

    headers = {
        "Authorization": f"Bearer {settings['api_key']}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/NourBradai/assistant_RH", # Optionnel pour OpenRouter
        "X-Title": "Assistant RH Candidate Filtering",              # Optionnel pour OpenRouter
    }

    messages = [
        {
            "role": "system",
            "content": (
                "Tu es un recruteur expert et chaleureux. Ton rôle est de mener un court entretien de présélection. "
                "Tu t'adresses DIRECTEMENT au candidat (vouvoiement 'vous'). "
                "Tes questions doivent être courtes, percutantes et sonner comme une vraie conversation humaine. "
                "Ne fais pas de listes techniques froides, intègre les éléments naturellement."
            )
        },
        {
            "role": "user",
            "content": prompt
        }
    ]

    payload: dict[str, Any] = {
        "model": settings["model"],
        "messages": messages,
        "temperature": 0.7, # Légèrement plus élevé pour plus de naturel
    }

    with httpx.Client(timeout=60.0) as client:
        response = client.post(settings["api_url"], headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


def fallback_generate_question(question: ChatQuestion) -> str:
    """
    Fallback local si aucun LLM n'est disponible.
    """
    return question.question_text


def normalize_text(text: str) -> str:
    return text.strip().lower() if text else ""


def fallback_analyze_answer(question: ChatQuestion, answer_text: str) -> QuestionAnalysis:
    """
    Analyse locale de secours, simple mais stable. 
    Plus généreuse pour les réponses affirmatives.
    """
    answer = normalize_text(answer_text)
    if not answer:
        return QuestionAnalysis(
            relevance_score=0.0,
            evidence_score=0.0,
            clarity_score=0.0,
            stance_score=0.0,
            final_answer_score=0.0,
            justification="Réponse vide ou absente."
        )

    # 1. Analyse de la position (Stance)
    negative_markers = ["non", "no", "never", "jamais", "pas encore"]
    partial_markers = ["pas directement", "partiellement", "un peu", "similar", "similaire"]
    positive_markers = ["oui", "yes", "used", "utilisé", "developed", "développé", "connais", "maîtrise", "expert"]

    if any(marker in answer for marker in negative_markers):
        stance_score = 25.0
    elif any(marker in answer for marker in partial_markers):
        stance_score = 65.0
    elif any(marker in answer for marker in positive_markers):
        stance_score = 90.0
    else:
        stance_score = 70.0

    # 2. Analyse de la pertinence (Relevance)
    expected = [s.lower() for s in question.expected_signals]
    matched_signals = sum(1 for signal in expected if signal in answer)
    # Base plus élevée si la position est positive
    base_relevance = 50.0 if stance_score >= 80.0 else 30.0
    relevance_score = min(100.0, base_relevance + matched_signals * 15.0)

    # 3. Analyse de la preuve (Evidence)
    evidence_markers = [
        "project", "projet", "stage", "internship", "mission",
        "client", "api", "backend", "developed", "développé",
        "implemented", "réalisé", "built", "used", "utilisé",
        "entreprise", "société", "pendant", "durant", "période"
    ]
    evidence_hits = sum(1 for marker in evidence_markers if marker in answer)
    base_evidence = 40.0 if len(answer.split()) > 10 else 25.0
    evidence_score = min(100.0, base_evidence + evidence_hits * 15.0)

    # 4. Analyse de la clarté (Clarity)
    word_count = len(answer.split())
    if word_count <= 2:
        clarity_score = 30.0
    elif word_count <= 7:
        clarity_score = 60.0
    elif word_count <= 15:
        clarity_score = 85.0
    else:
        clarity_score = 95.0

    final_answer_score = round(
        (0.35 * relevance_score)
        + (0.30 * evidence_score)
        + (0.20 * clarity_score)
        + (0.15 * stance_score),
        2
    )

    return QuestionAnalysis(
        relevance_score=round(relevance_score, 2),
        evidence_score=round(evidence_score, 2),
        clarity_score=round(clarity_score, 2),
        stance_score=round(stance_score, 2),
        final_answer_score=final_answer_score,
        justification="Analyse locale (mock mode) avec pondération optimisée pour la pertinence et les preuves."
    )


def parse_analysis_json(raw_text: str) -> QuestionAnalysis:
    """
    Transforme le JSON brut renvoyé par le LLM en objet QuestionAnalysis.
    """
    data = json.loads(raw_text)

    return QuestionAnalysis(
        relevance_score=float(data.get("relevance_score", 0.0)),
        evidence_score=float(data.get("evidence_score", 0.0)),
        clarity_score=float(data.get("clarity_score", 0.0)),
        stance_score=float(data.get("stance_score", 0.0)),
        final_answer_score=float(data.get("final_answer_score", 0.0)),
        justification=str(data.get("justification", "")),
    )


def generate_question_with_llm(
    question: ChatQuestion,
    job: JobRequirement,
    candidate: CandidateCV,
) -> str:
    """
    Génère la version visible de la question.
    Si le LLM n'est pas configuré, retourne la question locale.
    """
    if not llm_is_configured():
        return fallback_generate_question(question)

    try:
        prompt = build_question_generation_prompt(question, job, candidate)
        generated_text = call_openai_compatible_api(prompt)

        if not generated_text:
            return fallback_generate_question(question)

        return generated_text
    except Exception:
        return fallback_generate_question(question)


def analyze_answer_with_llm(
    question: ChatQuestion,
    answer_text: str,
    job: JobRequirement,
    candidate: CandidateCV,
) -> QuestionAnalysis:
    """
    Analyse une réponse avec le LLM si possible.
    Sinon utilise une analyse locale de secours.
    """
    if not llm_is_configured():
        return fallback_analyze_answer(question, answer_text)

    try:
        prompt = build_answer_analysis_prompt(question, answer_text, job, candidate)
        raw_response = call_openai_compatible_api(prompt)
        return parse_analysis_json(raw_response)
    except Exception:
        return fallback_analyze_answer(question, answer_text)
