from app.models.schemas import (
    ChatQuestion,
    ChatTurn,
    QuestionAnalysis,
    JobRequirement,
    CandidateCV,
)
from app.services.llm_client import analyze_answer_with_llm


def normalize_text(text: str) -> str:
    """
    Nettoie légèrement le texte pour éviter les faux cas vides.
    """
    return text.strip() if text else ""


def is_valid_answer(answer_text: str) -> bool:
    """
    Vérifie si une réponse est exploitable.
    Une réponse vide ou composée uniquement d'espaces est invalide.
    """
    return bool(normalize_text(answer_text))


def build_empty_analysis(reason: str = "Réponse vide ou non exploitable.") -> QuestionAnalysis:
    """
    Construit une analyse par défaut si la réponse est vide.
    """
    return QuestionAnalysis(
        relevance_score=0.0,
        evidence_score=0.0,
        clarity_score=0.0,
        stance_score=0.0,
        final_answer_score=0.0,
        justification=reason,
    )


def analyze_single_answer(
    question: ChatQuestion,
    answer_text: str,
    job: JobRequirement,
    candidate: CandidateCV,
) -> QuestionAnalysis:
    """
    Analyse une seule réponse.
    Si la réponse est vide, retourne une analyse vide.
    Sinon délègue au client LLM (ou au fallback local intégré au client).
    """
    cleaned_answer = normalize_text(answer_text)

    if not is_valid_answer(cleaned_answer):
        return build_empty_analysis()

    analysis = analyze_answer_with_llm(
        question=question,
        answer_text=cleaned_answer,
        job=job,
        candidate=candidate,
    )

    return analysis


def build_chat_turn(
    question: ChatQuestion,
    answer_text: str,
    job: JobRequirement,
    candidate: CandidateCV,
) -> ChatTurn:
    """
    Construit un tour de conversation complet :
    - question
    - réponse
    - analyse
    """
    analysis = analyze_single_answer(
        question=question,
        answer_text=answer_text,
        job=job,
        candidate=candidate,
    )

    return ChatTurn(
        question=question,
        answer_text=normalize_text(answer_text),
        analysis=analysis,
    )


def analyze_multiple_answers(
    questions: list[ChatQuestion],
    answers: list[str],
    job: JobRequirement,
    candidate: CandidateCV,
) -> list[ChatTurn]:
    """
    Analyse plusieurs réponses d'un coup.
    Utile si on veut traiter un lot de questions/réponses.
    """
    turns: list[ChatTurn] = []

    count = min(len(questions), len(answers))

    for i in range(count):
        turn = build_chat_turn(
            question=questions[i],
            answer_text=answers[i],
            job=job,
            candidate=candidate,
        )
        turns.append(turn)

    return turns