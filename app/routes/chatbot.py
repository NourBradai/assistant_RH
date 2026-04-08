"""
Routes pour le fonctionnement du Chatbot de présélection.
Version Requirement-Driven : cible les ambiguïtés du screening.
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.models.schemas import (
    ChatbotSession,
    StartChatbotRequest,
    SubmitAnswerRequest,
    ParsedJobProfile,
    ParsedCandidateProfile,
    EnhancedScreeningResult
)
from app.database import get_db
from app.models.orm import JobModel, CandidateModel, ScreeningResultModel, ChatbotSessionModel
from app.services.interview_planner import build_interview_plan
from app.services.llm_client import generate_question_with_llm
from app.services.response_analyzer import build_chat_turn
from app.services.chatbot_aggregator import finalize_chatbot_session, build_recruiter_summary
import uuid

router = APIRouter()

def get_job_by_id(job_id: str, db: Session):
    db_job = db.query(JobModel).filter(JobModel.job_id == job_id).first()
    return ParsedJobProfile(**db_job.data) if db_job else None

def get_candidate_by_id(candidate_id: str, db: Session):
    db_c = db.query(CandidateModel).filter(CandidateModel.candidate_id == candidate_id).first()
    return ParsedCandidateProfile(**db_c.data) if db_c else None

def get_screening_by_job_and_candidate(job_id: str, candidate_id: str, db: Session):
    db_s = db.query(ScreeningResultModel).filter(
        ScreeningResultModel.job_id == job_id, 
        ScreeningResultModel.candidate_id == candidate_id
    ).first()
    return EnhancedScreeningResult(**db_s.data) if db_s else None

def get_session_by_id(session_id: str, db: Session) -> ChatbotSession:
    db_sess = db.query(ChatbotSessionModel).filter(ChatbotSessionModel.session_id == session_id).first()
    if not db_sess:
        raise HTTPException(status_code=404, detail="Session chatbot non trouvée")
    return ChatbotSession(**db_sess.data)

def save_session(session: ChatbotSession, db: Session):
    db_sess = db.query(ChatbotSessionModel).filter(ChatbotSessionModel.session_id == session.session_id).first()
    if db_sess:
        db_sess.status = session.status
        db_sess.data = session.model_dump()
    else:
        db_sess = ChatbotSessionModel(
            session_id=session.session_id,
            job_id=session.job_id,
            candidate_id=session.candidate_id,
            status=session.status,
            data=session.model_dump()
        )
        db.add(db_sess)
    db.commit()

@router.post("/start")
def start_chatbot_session(payload: StartChatbotRequest, db: Session = Depends(get_db)):
    """
    Démarre une session chatbot basée sur les exigences non validées.
    """
    job = get_job_by_id(payload.job_id, db)
    candidate = get_candidate_by_id(payload.candidate_id, db)
    screening = get_screening_by_job_and_candidate(payload.job_id, payload.candidate_id, db)

    if not all([job, candidate, screening]):
        raise HTTPException(status_code=404, detail="Job, Candidate or Screening result not found")

    if not isinstance(screening, EnhancedScreeningResult):
        raise HTTPException(status_code=400, detail="Initial screening must be in 'enhanced' format")

    # Génération du plan basé sur les 'to_validate'
    questions = build_interview_plan(job, candidate, screening)

    # Reformulation LLM
    for q in questions:
        q.question_text = generate_question_with_llm(q, job, candidate)

    session = ChatbotSession(
        session_id=str(uuid.uuid4()),
        job_id=payload.job_id,
        candidate_id=payload.candidate_id,
        initial_score=screening.overall_score,
        initial_screening=screening,
        questions=questions,
        turns=[],
        current_index=0
    )

    save_session(session, db)

    # Si pas de questions, on finalise
    if not session.questions:
        session = finalize_chatbot_session(session)
        save_session(session, db)
        return {
            "message": "Session finalisée (aucune question nécessaire).",
            "session_id": session.session_id,
            "status": session.status,
            "summary": build_recruiter_summary(session)
        }

    return {
        "message": "Session chatbot démarrée",
        "session_id": session.session_id,
        "total_questions": len(session.questions),
        "first_question": session.questions[0]
    }

@router.post("/answer")
def submit_answer(payload: SubmitAnswerRequest, db: Session = Depends(get_db)):
    """
    Reçoit la réponse, l'analyse et passe à la suite.
    """
    session = get_session_by_id(payload.session_id, db)
    if session.status == "completed":
        raise HTTPException(status_code=400, detail="Session déjà terminée")

    current_q = session.questions[session.current_index]
    
    # Analyse de la réponse (LLM)
    turn = build_chat_turn(current_q, payload.answer_text)
    session.turns.append(turn)
    session.current_index += 1

    if session.current_index >= len(session.questions):
        session = finalize_chatbot_session(session)
        save_session(session, db)
        return {
            "message": "Entretien terminé",
            "session_id": session.session_id,
            "status": session.status,
            "final_score": session.final_score,
            "summary": build_recruiter_summary(session)
        }

    save_session(session, db)
    return {
        "message": "Réponse enregistrée",
        "next_question": session.questions[session.current_index],
        "progress": f"{session.current_index}/{len(session.questions)}"
    }

@router.get("/status/{session_id}")
def get_session_status(session_id: str, db: Session = Depends(get_db)):
    session = get_session_by_id(session_id, db)
    return session