"""
Routes pour la gestion des offres d'emploi (Jobs).
Supporte l'extraction automatique des exigences par LLM.
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.models.schemas import JobRequirement, ParsedJobProfile
from app.database import get_db
from app.models.orm import JobModel
from app.services.job_parser import parse_job_description

router = APIRouter()

@router.post("/")
def create_job(job: ParsedJobProfile, db: Session = Depends(get_db)):
    """
    Crée une offre d'emploi déjà structurée.
    """
    db_job = JobModel(
        job_id=job.job_id,
        title=job.title,
        data=job.model_dump()
    )
    db.add(db_job)
    db.commit()
    return {"message": "Job registered successfully", "job_id": job.job_id}

@router.post("/parse")
def parse_and_create_job(raw_text: str, db: Session = Depends(get_db)):
    """
    Analyse un texte brut d'offre d'emploi et crée un profil d'exigences structuré.
    """
    try:
        profile = parse_job_description(raw_text)
        db_job = JobModel(
            job_id=profile.job_id,
            title=profile.title,
            data=profile.model_dump()
        )
        db.add(db_job)
        db.commit()
        return {"message": "Job parsed and created", "profile": profile}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing job: {str(e)}")

@router.get("/")
def list_jobs(db: Session = Depends(get_db)):
    """
    Liste toutes les offres (Profils structurés).
    """
    jobs = db.query(JobModel).all()
    # On renvoie les ParsedJobProfile reconstitués
    return [ParsedJobProfile(**j.data) for j in jobs]

@router.get("/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    """
    Récupère une offre spécifique.
    """
    job = db.query(JobModel).filter(JobModel.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return ParsedJobProfile(**job.data)