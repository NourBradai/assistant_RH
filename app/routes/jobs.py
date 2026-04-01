"""
Routes pour la gestion des offres d'emploi (Jobs).
Permet de créer et de lister les besoins de recrutement.
"""
from fastapi import APIRouter
from app.models.schemas import JobRequirement
from app.database import mock_jobs

router = APIRouter()

@router.post("/")
def create_job(job: JobRequirement):
    """
    Crée une nouvelle offre d'emploi avec ses critères et ses poids de scoring.
    """
    mock_jobs.append(job)
    return {"message": "Job created successfully", "job": job}

@router.get("/")
def list_jobs():
    """
    Liste toutes les offres d'emploi enregistrées.
    """
    return mock_jobs