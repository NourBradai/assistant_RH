import uuid
from fastapi import APIRouter, HTTPException
from app.models.schemas import (
    ChatbotSession,
    StartChatbotRequest,
    SubmitAnswerRequest,
)
from app.database import mock_jobs, mock_candidates, mock_screening_results, mock_chatbot_sessions
from app.services.interview_planner import build_interview_plan
from app.services.llm_client import generate_question_with_llm
from app.services.response_analyzer import build_chat_turn
from app.services.chatbot_aggregator import finalize_chatbot_session, build_recruiter_summary

router = APIRouter()


def get_job_by_id(job_id: str):
    """
    Récupère un job depuis la base simulée.
    """
    return next((j for j in mock_jobs if j.job_id == job_id), None)


def get_candidate_by_id(candidate_id: str):
    """
    Récupère un candidat depuis la base simulée.
    """
    return next((c for c in mock_candidates if c.candidate_id == candidate_id), None)


def get_screening_by_job_and_candidate(job_id: str, candidate_id: str):
    """
    Récupère le résultat du screening initial.
    """
    return next(
        (
            s for s in mock_screening_results
            if s.job_id == job_id and s.candidate_id == candidate_id
        ),
        None
    )


def get_session_by_id(session_id: str) -> ChatbotSession:
    """
    Récupère une session chatbot par ID.
    """
    session = mock_chatbot_sessions.get(session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session chatbot avec l'ID {session_id} non trouvée"
        )
    return session


@router.post("/start")
def start_chatbot_session(payload: StartChatbotRequest):
    """
    Démarre une session chatbot :
    - récupère le job, le candidat et le screening initial
    - construit le plan d'entretien
    - reformule les questions avec le LLM
    - crée la session
    - retourne la première question
    """
    job = get_job_by_id(payload.job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job avec l'ID {payload.job_id} non trouvé"
        )

    candidate = get_candidate_by_id(payload.candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidat avec l'ID {payload.candidate_id} non trouvé"
        )

    screening = get_screening_by_job_and_candidate(payload.job_id, payload.candidate_id)
    if not screening:
        raise HTTPException(
            status_code=404,
            detail="Aucun screening initial trouvé pour ce job et ce candidat"
        )

    # Construire le plan logique
    questions = build_interview_plan(job, candidate, screening)

    # Reformuler les questions avec le LLM (ou fallback local)
    for question in questions:
        generated_text = generate_question_with_llm(question, job, candidate)
        question.question_text = generated_text

    session = ChatbotSession(
        session_id=str(uuid.uuid4()),
        job_id=payload.job_id,
        candidate_id=payload.candidate_id,
        initial_score=screening.initial_score,
        questions=questions,
        turns=[],
        current_index=0,
        chatbot_score=0.0,
        final_score=0.0,
        final_decision="pending",
        status="active",
    )

    # Si aucune question n'est nécessaire, on finalise immédiatement
    if not session.questions:
        session = finalize_chatbot_session(session)
        mock_chatbot_sessions[session.session_id] = session

        return {
            "message": "Aucune question supplémentaire nécessaire. Session finalisée automatiquement.",
            "session_id": session.session_id,
            "status": session.status,
            "chatbot_score": session.chatbot_score,
            "final_score": session.final_score,
            "final_decision": session.final_decision,
            "recruiter_summary": build_recruiter_summary(session),
        }

    mock_chatbot_sessions[session.session_id] = session

    first_question = session.questions[0]

    return {
        "message": "Session chatbot démarrée avec succès",
        "session_id": session.session_id,
        "status": session.status,
        "current_index": session.current_index,
        "total_questions": len(session.questions),
        "question": first_question,
    }


@router.get("/current")
def get_current_question(session_id: str):
    """
    Retourne la question actuelle d'une session chatbot.
    """
    session = get_session_by_id(session_id)

    if session.status == "completed":
        return {
            "message": "La session est déjà terminée",
            "session_id": session.session_id,
            "status": session.status,
            "current_index": session.current_index,
            "total_questions": len(session.questions),
            "question": None,
        }

    if session.current_index >= len(session.questions):
        return {
            "message": "Il n'y a plus de question en attente",
            "session_id": session.session_id,
            "status": session.status,
            "current_index": session.current_index,
            "total_questions": len(session.questions),
            "question": None,
        }

    current_question = session.questions[session.current_index]

    return {
        "session_id": session.session_id,
        "status": session.status,
        "current_index": session.current_index,
        "total_questions": len(session.questions),
        "question": current_question,
    }


@router.post("/answer")
def submit_answer(payload: SubmitAnswerRequest):
    """
    Reçoit la réponse à la question courante :
    - analyse la réponse
    - ajoute un ChatTurn à la session
    - avance à la question suivante
    - ou finalise la session si c'était la dernière
    """
    session = get_session_by_id(payload.session_id)

    if session.status == "completed":
        raise HTTPException(
            status_code=400,
            detail="Cette session est déjà terminée"
        )

    if session.current_index >= len(session.questions):
        raise HTTPException(
            status_code=400,
            detail="Il n'y a plus de question à laquelle répondre"
        )

    job = get_job_by_id(session.job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job avec l'ID {session.job_id} non trouvé"
        )

    candidate = get_candidate_by_id(session.candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidat avec l'ID {session.candidate_id} non trouvé"
        )

    current_question = session.questions[session.current_index]

    # Construire le tour de conversation complet
    turn = build_chat_turn(
        question=current_question,
        answer_text=payload.answer_text,
        job=job,
        candidate=candidate,
    )

    session.turns.append(turn)
    session.current_index += 1

    # Si toutes les questions sont terminées -> finalisation
    if session.current_index >= len(session.questions):
        session = finalize_chatbot_session(session)
        mock_chatbot_sessions[session.session_id] = session

        return {
            "message": "Réponse enregistrée. La session est maintenant terminée.",
            "session_id": session.session_id,
            "status": session.status,
            "last_turn": turn,
            "chatbot_score": session.chatbot_score,
            "final_score": session.final_score,
            "final_decision": session.final_decision,
            "recruiter_summary": build_recruiter_summary(session),
            "next_question": None,
        }

    # Sinon, on retourne la question suivante
    next_question = session.questions[session.current_index]
    mock_chatbot_sessions[session.session_id] = session

    return {
        "message": "Réponse enregistrée avec succès",
        "session_id": session.session_id,
        "status": session.status,
        "last_turn": turn,
        "current_index": session.current_index,
        "total_questions": len(session.questions),
        "next_question": next_question,
    }


@router.get("/final")
def get_final_chatbot_result(session_id: str):
    """
    Retourne le résultat final d'une session chatbot.
    Si la session n'est pas encore terminée, on retourne quand même l'état actuel.
    """
    session = get_session_by_id(session_id)

    # Si la session est déjà terminée, on ne recalcule pas.
    # Sinon, on peut fournir un état intermédiaire.
    if session.status == "completed":
        return {
            "session_id": session.session_id,
            "status": session.status,
            "job_id": session.job_id,
            "candidate_id": session.candidate_id,
            "initial_score": session.initial_score,
            "chatbot_score": session.chatbot_score,
            "final_score": session.final_score,
            "final_decision": session.final_decision,
            "answered_questions": len(session.turns),
            "total_questions": len(session.questions),
            "turns": session.turns,
            "recruiter_summary": build_recruiter_summary(session),
        }

    return {
        "session_id": session.session_id,
        "status": session.status,
        "job_id": session.job_id,
        "candidate_id": session.candidate_id,
        "initial_score": session.initial_score,
        "answered_questions": len(session.turns),
        "total_questions": len(session.questions),
        "turns": session.turns,
        "message": "La session n'est pas encore terminée. Le score final n'est donc pas définitif.",
    }