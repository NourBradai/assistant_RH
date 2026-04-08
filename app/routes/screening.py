"""
Routes pour l'algorithme de screening (Version Requirement-Driven).
Utilise le matcher sémantique par exigences.
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.models.schemas import EnhancedScreeningResult, ParsedJobProfile, ParsedCandidateProfile
from app.services.matcher import match_job_to_candidate
from app.database import get_db
from app.models.orm import JobModel, CandidateModel, ScreeningResultModel
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