"""
Analyseur de réponses du chatbot.
Délègue au LLM pour transformer une réponse libre en scores de validation d'exigence.
"""
from app.models.schemas import ChatQuestion, ChatTurn, QuestionAnalysis
from app.services.llm_client import analyze_answer_with_llm

def analyze_single_answer(
    question: ChatQuestion,
    answer_text: str
) -> QuestionAnalysis:
    """
    Analyse une réponse du candidat à une question ciblée sur une exigence.
    """
    if not answer_text or not answer_text.strip():
        return QuestionAnalysis(
            relevance_score=0,
            evidence_score=0,
            clarity_score=0,
            stance_score=0,
            final_answer_score=0,
            updated_requirement_confidence=0,
            justification="Réponse vide."
        )

    return analyze_answer_with_llm(question, answer_text)

def build_chat_turn(
    question: ChatQuestion,
    answer_text: str
) -> ChatTurn:
    """
    Construit un tour de conversation complet.
    """
    analysis = analyze_single_answer(question, answer_text)
    return ChatTurn(
        question=question,
        answer_text=answer_text.strip(),
        analysis=analysis
    )