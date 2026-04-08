import json
import os
from typing import Any, Optional

import httpx

from app.models.schemas import (
    ChatQuestion,
    QuestionAnalysis,
    JobRequirement,
    CandidateCV,
    ParsedJobProfile,
    ParsedCandidateProfile
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
    job: ParsedJobProfile,
    candidate: ParsedCandidateProfile,
) -> str:
    """
    Construit le prompt de génération de question (Reformulation naturelle).
    """
    return f"""
Tu es un assistant de présélection RH expert et chaleureux.
Ta tâche : reformuler UNE seule question de manière naturelle, professionnelle et humaine.

Règles :
- Ne mentionne pas de listes techniques froides.
- Utilise le contexte du CV (sections, preuves trouvées) pour personnaliser la question.
- Ta question doit ressembler à une interaction réelle (vouvoiement).
- Réponds UNIQUEMENT par la question.

Contexte du poste : {job.title}
Exigence visée : {question.objective}

Question interne de base : {question.question_text}

Produis maintenant la meilleure reformulation.
""".strip()


def build_answer_analysis_prompt(
    question: ChatQuestion,
    answer_text: str,
) -> str:
    """
    Construit le prompt d'analyse d'une réponse.
    Force le LLM à répondre en JSON.
    """
    return f"""
Tu es un expert RH analysant une réponse de candidat.
Analyse la réponse par rapport à l'exigence : {question.objective}

JSON STRICT UNIQUEMENT :
{{
  "relevance_score": 0-100,
  "evidence_score": 0-100,
  "clarity_score": 0-100,
  "stance_score": 0-100,
  "final_answer_score": 0-100,
  "updated_requirement_confidence": 0-100,  # Confiance finale dans la maîtrise de l'exigence
  "justification": "..."
}}

Réponse à analyser :
{answer_text}
""".strip()


def call_openai_compatible_api(prompt: str) -> str:
    """
    Appelle une API compatible OpenAI.
    """
    settings = get_llm_settings()
    headers = {"Authorization": f"Bearer {settings['api_key']}", "Content-Type": "application/json"}
    
    messages = [
        {"role": "system", "content": "Tu es un recruteur expert. Tu réponds de manière concise et directe."},
        {"role": "user", "content": prompt}
    ]

    payload = {"model": settings["model"], "messages": messages, "temperature": 0.3}

    with httpx.Client(timeout=60.0) as client:
        response = client.post(settings["api_url"], headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()


def extract_job_requirements_with_llm(raw_text: str) -> dict:
    """
    Extrait les exigences structurées d'une offre d'emploi.
    """
    prompt = f"""
Analyse cette offre d'emploi et extrais TOUTES les exigences en JSON.

Structure souhaitée :
{{
  "job_title": "...",
  "requirements": [
    {{
      "type": "skill|experience|degree|language|seniority|constraint",
      "label": "Nom de l'exigence",
      "importance": "low|medium|high|critical",
      "required_level": "...",
      "description": "...",
      "category": "..."
    }}
  ]
}}

OFFRE :
{raw_text}
""".strip()

    if not llm_is_configured():
        return {"job_title": "Poste", "requirements": []}

    try:
        raw_response = call_openai_compatible_api(prompt)
        # Nettoyage JSON
        clean_json = raw_response.strip()
        if clean_json.startswith("```"):
            clean_json = clean_json.split("\n", 1)[1].rsplit("\n", 1)[0].strip()
            if clean_json.startswith("json"): clean_json = clean_json[4:].strip()
        return json.loads(clean_json)
    except Exception:
        return {"job_title": "Error", "requirements": []}



def parse_analysis_json(raw_text: str) -> QuestionAnalysis:
    """
    Parse le JSON d'analyse.
    """
    clean_json = raw_text.strip()
    if clean_json.startswith("```"):
        clean_json = clean_json.split("\n", 1)[1].rsplit("\n", 1)[0].strip()
        if clean_json.startswith("json"): clean_json = clean_json[4:].strip()
    
    data = json.loads(clean_json)
    return QuestionAnalysis(
        relevance_score=float(data.get("relevance_score", 0.0)),
        evidence_score=float(data.get("evidence_score", 0.0)),
        clarity_score=float(data.get("clarity_score", 0.0)),
        stance_score=float(data.get("stance_score", 0.0)),
        final_answer_score=float(data.get("final_answer_score", 0.0)),
        updated_requirement_confidence=float(data.get("updated_requirement_confidence", 0.0)),
        justification=str(data.get("justification", ""))
    )


def generate_question_with_llm(question: ChatQuestion, job: ParsedJobProfile, candidate: ParsedCandidateProfile) -> str:
    if not llm_is_configured(): return question.question_text
    try:
        prompt = build_question_generation_prompt(question, job, candidate)
        return call_openai_compatible_api(prompt)
    except Exception: return question.question_text


def _local_analyze_answer(question: ChatQuestion, answer_text: str) -> QuestionAnalysis:
    """
    Analyse locale de secours quand le LLM n'est pas disponible.
    Basée sur des signaux textuels simples (longueur, mots-clés positifs, preuves).
    """
    text = answer_text.lower().strip()
    words = text.split()

    # 1. Stance (position affirmative / négative)
    negative_markers = ["non", "no", "never", "jamais", "pas encore", "n'ai pas"]
    partial_markers  = ["partiellement", "un peu", "similaire", "pas directement"]
    positive_markers = ["oui", "yes", "utilisé", "developed", "réalisé", "maîtrise", "expert", "travaillé", "projet"]

    if any(m in text for m in negative_markers):
        stance_score = 20.0
    elif any(m in text for m in partial_markers):
        stance_score = 55.0
    elif any(m in text for m in positive_markers):
        stance_score = 90.0
    else:
        stance_score = 65.0

    # 2. Relevance (signaux de la question)
    expected = [s.lower() for s in question.expected_signals]
    matched_signals = sum(1 for s in expected if s in text)
    base_rel = 50.0 if stance_score >= 80 else 30.0
    relevance_score = min(100.0, base_rel + matched_signals * 10.0)

    # 3. Evidence (preuves concrètes)
    evidence_markers = ["projet", "stage", "mission", "client", "entreprise",
                        "api", "backend", "réalisé", "développé", "pendant", "chez"]
    evidence_hits = sum(1 for m in evidence_markers if m in text)
    base_ev = 40.0 if len(words) > 12 else 20.0
    evidence_score = min(100.0, base_ev + evidence_hits * 10.0)

    # 4. Clarity (longueur de la réponse)
    if len(words) <= 2:    clarity_score = 25.0
    elif len(words) <= 7:  clarity_score = 55.0
    elif len(words) <= 15: clarity_score = 80.0
    else:                  clarity_score = 95.0

    final_answer_score = round(
        0.35 * relevance_score + 0.30 * evidence_score +
        0.20 * clarity_score   + 0.15 * stance_score, 2
    )

    # updated_requirement_confidence = confiance globale qu'on peut déduire localement
    updated_req_confidence = round(
        0.5 * evidence_score + 0.3 * stance_score + 0.2 * relevance_score, 2
    )

    return QuestionAnalysis(
        relevance_score=round(relevance_score, 2),
        evidence_score=round(evidence_score, 2),
        clarity_score=round(clarity_score, 2),
        stance_score=round(stance_score, 2),
        final_answer_score=final_answer_score,
        updated_requirement_confidence=updated_req_confidence,
        justification="Analyse locale (mode mock) — basée sur mots-clés et longueur de réponse."
    )


def analyze_answer_with_llm(question: ChatQuestion, answer_text: str) -> QuestionAnalysis:
    if not llm_is_configured():
        return _local_analyze_answer(question, answer_text)
    try:
        prompt = build_answer_analysis_prompt(question, answer_text)
        return parse_analysis_json(call_openai_compatible_api(prompt))
    except Exception as e:
        return _local_analyze_answer(question, answer_text)
