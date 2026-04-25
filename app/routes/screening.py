"""
Routes pour l'algorithme de screening (Version Requirement-Driven).
Utilise le matcher sémantique par exigences.
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.schemas import EnhancedScreeningResult, ParsedJobProfile, ParsedCandidateProfile
from app.services.matcher import match_job_to_candidate
from app.database import get_db
from app.models.orm import JobModel, CandidateModel, ScreeningResultModel, ChatbotSessionModel
import uuid

router = APIRouter()

def save_screening_result(result: EnhancedScreeningResult, db: Session):
    """
    Sauvegarde le résultat enrichi dans la DB (upsert).
    """
    db_res = db.query(ScreeningResultModel).filter(
        ScreeningResultModel.job_id == result.job_id,
        ScreeningResultModel.candidate_id == result.candidate_id
    ).first()
    
    if db_res:
        db_res.overall_score = result.overall_score
        db_res.status = result.status
        db_res.data = result.model_dump()
    else:
        db_res = ScreeningResultModel(
            id=f"scr_{uuid.uuid4().hex[:8]}",
            job_id=result.job_id,
            candidate_id=result.candidate_id,
            overall_score=result.overall_score,
            status=result.status,
            data=result.model_dump()
        )
        db.add(db_res)
    db.commit()

@router.get("/jobs/{job_id}/match/{candidate_id}")
def match_candidate_to_job(job_id: str, candidate_id: str, db: Session = Depends(get_db)):
    """
    Route principale de matching : compare un profil candidat structuré à une offre structurée.
    """
    db_job = db.query(JobModel).filter(JobModel.job_id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")

    db_candidate = db.query(CandidateModel).filter(CandidateModel.candidate_id == candidate_id).first()
    if not db_candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    job = ParsedJobProfile(**db_job.data)
    candidate = ParsedCandidateProfile(**db_candidate.data)

    result = match_job_to_candidate(job, candidate)
    save_screening_result(result, db)
    return result


from app.models.schemas import EnhancedScreeningResult, ParsedJobProfile, ParsedCandidateProfile, BatchMatchRequest

@router.post("/jobs/{job_id}/match-all")
def match_all_candidates_to_job(job_id: str, req: Optional[BatchMatchRequest] = None, db: Session = Depends(get_db)):
    """
    Match candidates in the database to a specific job.
    If req.candidate_ids is provided, only matches those. Otherwise matches ALL.
    """
    db_job = db.query(JobModel).filter(JobModel.job_id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")

    job = ParsedJobProfile(**db_job.data)
    
    query = db.query(CandidateModel)
    if req and req.candidate_ids:
        query = query.filter(CandidateModel.candidate_id.in_(req.candidate_ids))
    
    candidates = query.all()

    if not candidates:
        raise HTTPException(status_code=404, detail="No matching candidates found")

    results = []
    for db_c in candidates:
        candidate = ParsedCandidateProfile(**db_c.data)
        result = match_job_to_candidate(job, candidate)
        save_screening_result(result, db)
        results.append({
            "candidate_id": result.candidate_id,
            "name": db_c.name,
            "overall_score": result.overall_score,
            "status": result.status,
            "summary": result.summary,
            "requirement_matches": result.requirement_matches
        })

    # Sort by score descending
    results.sort(key=lambda x: x["overall_score"], reverse=True)

    return {
        "job_id": job_id,
        "job_title": job.title,
        "total_candidates": len(results),
        "shortlisted": sum(1 for r in results if r["status"] == "shortlisted"),
        "potential": sum(1 for r in results if r["status"] == "potential"),
        "rejected": sum(1 for r in results if r["status"] == "rejected"),
        "results": results
    }


@router.get("/jobs/{job_id}/candidates")
def get_candidates_for_job(job_id: str, candidate_ids: Optional[List[str]] = None, db: Session = Depends(get_db)):
    """
    Retrieve screening results for a specific job, sorted by score.
    If candidate_ids is provided (as query params), only returns those.
    Used by the recruiter dashboard.
    """
    db_job = db.query(JobModel).filter(JobModel.job_id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")

    query = db.query(ScreeningResultModel).filter(ScreeningResultModel.job_id == job_id)
    if candidate_ids:
        query = query.filter(ScreeningResultModel.candidate_id.in_(candidate_ids))
    
    screenings = query.order_by(ScreeningResultModel.overall_score.desc()).all()

    results = []
    for s in screenings:
        # Get candidate name
        db_c = db.query(CandidateModel).filter(CandidateModel.candidate_id == s.candidate_id).first()
        name = db_c.name if db_c else "Inconnu"
        
        # Check if chatbot session exists
        chatbot = db.query(ChatbotSessionModel).filter(
            ChatbotSessionModel.job_id == job_id,
            ChatbotSessionModel.candidate_id == s.candidate_id
        ).first()
        
        chatbot_info = None
        if chatbot:
            session_data = chatbot.data or {}
            chatbot_info = {
                "session_id": chatbot.session_id,
                "status": chatbot.status,
                "final_score": session_data.get("final_score", 0),
                "final_decision": session_data.get("final_decision", "pending"),
                "chatbot_score": session_data.get("chatbot_score", 0),
            }

        results.append({
            "candidate_id": s.candidate_id,
            "name": name,
            "overall_score": s.overall_score,
            "status": s.status,
            "screening_data": EnhancedScreeningResult(**s.data) if s.data else None,
            "chatbot": chatbot_info,
        })

    return {
        "job_id": job_id,
        "job_title": ParsedJobProfile(**db_job.data).title,
        "candidates": results
    }