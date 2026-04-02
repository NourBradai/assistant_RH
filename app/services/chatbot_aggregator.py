from app.models.schemas import ChatTurn, ChatbotSession


def compute_weighted_chatbot_score(turns: list[ChatTurn]) -> float:
    """
    Calcule le score chatbot global à partir des tours analysés.
    Utilise une moyenne pondérée selon le poids des questions.
    """
    if not turns:
        return 0.0

    weighted_sum = 0.0
    total_weight = 0.0

    for turn in turns:
        if not turn.analysis:
            continue

        question_weight = turn.question.weight
        answer_score = turn.analysis.final_answer_score

        weighted_sum += answer_score * question_weight
        total_weight += question_weight

    if total_weight == 0:
        return 0.0

    return round(weighted_sum / total_weight, 2)


def compute_final_score(
    initial_score: float,
    chatbot_score: float,
    screening_weight: float = 0.7,
    chatbot_weight: float = 0.3,
) -> float:
    """
    Combine le score initial du screening et le score du chatbot.
    """
    final_score = (screening_weight * initial_score) + (chatbot_weight * chatbot_score)
    return round(final_score, 2)


def get_final_decision(final_score: float) -> str:
    """
    Transforme le score final en décision finale.
    """
    if final_score >= 75:
        return "recommended"
    if final_score >= 55:
        return "review"
    return "rejected"


def count_answered_turns(turns: list[ChatTurn]) -> int:
    """
    Compte le nombre de tours effectivement répondus.
    """
    count = 0
    for turn in turns:
        if turn.answer_text and turn.analysis:
            count += 1
    return count


def build_recruiter_summary(session: ChatbotSession) -> str:
    """
    Construit un résumé synthétique pour le recruteur.
    """
    answered_turns = count_answered_turns(session.turns)

    if answered_turns == 0:
        return "Aucune réponse exploitable n’a été fournie par le candidat durant la phase chatbot."

    strong_answers = 0
    weak_answers = 0

    for turn in session.turns:
        if not turn.analysis:
            continue

        score = turn.analysis.final_answer_score
        if score >= 70:
            strong_answers += 1
        elif score < 40:
            weak_answers += 1

    return (
        f"Le candidat a répondu à {answered_turns} question(s). "
        f"{strong_answers} réponse(s) sont jugées solides, "
        f"{weak_answers} réponse(s) sont jugées faibles. "
        f"Le score chatbot est de {session.chatbot_score}/100 "
        f"et le score final est de {session.final_score}/100."
    )


def finalize_chatbot_session(session: ChatbotSession) -> ChatbotSession:
    """
    Met à jour la session avec :
    - chatbot_score
    - final_score
    - final_decision
    - status
    """
    chatbot_score = compute_weighted_chatbot_score(session.turns)
    final_score = compute_final_score(session.initial_score, chatbot_score)
    final_decision = get_final_decision(final_score)

    session.chatbot_score = chatbot_score
    session.final_score = final_score
    session.final_decision = final_decision
    session.status = "completed"

    return session