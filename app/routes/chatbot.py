"""
Routes pour le chatbot de pré-sélection.
Gère le démarrage de sessions personnalisées et la soumission des réponses des candidats.
"""
from fastapi import APIRouter, HTTPException
from app.models.schemas import ChatbotSession
from app.database import mock_jobs, mock_candidates, mock_screening_results, mock_chatbot_sessions
from app.services.question_generator import generate_chatbot_questions

router = APIRouter()

@router.get("/questions")
def get_chatbot_questions(job_id: str, candidate_id: str):
    """
    Génère les questions du chatbot à partir du job, du candidat et du screening.
    """
    job = next((j for j in mock_jobs if j.job_id == job_id), None)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job avec l'ID {job_id} non trouvé")

    candidate = next((c for c in mock_candidates if c.candidate_id == candidate_id), None)
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidat avec l'ID {candidate_id} non trouvé")

    screening = next(
        (s for s in mock_screening_results if s.job_id == job_id and s.candidate_id == candidate_id),
        None
    )
    if not screening:
        raise HTTPException(
            status_code=404,
            detail="Aucun résultat de screening trouvé. Veuillez d'abord appeler la route de matching."
        )

    questions = generate_chatbot_questions(job, candidate, screening)

    return {
        "job_id": job_id,
        "candidate_id": candidate_id,
        "questions": questions
    }

@router.post("/submit")
def submit_chatbot_session(session: ChatbotSession):
    """
    Reçoit les réponses du candidat au chatbot.
    """
    mock_chatbot_sessions.append(session)
    return {
        "message": "Chatbot session received successfully",
        "session": session
    }