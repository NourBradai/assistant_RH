"""
Routes pour la gestion des candidats et de leurs CVs.
Supporte l'ajout manuel et l'upload de fichiers PDF avec extraction automatique.
"""
from fastapi import APIRouter, UploadFile, File
from app.models.schemas import CandidateCV
from app.services.cv_parser import parse_cv_pdf
from app.database import mock_candidates

router = APIRouter()

@router.post("/")
def add_candidate(cv: CandidateCV):
    """
    Ajoute manuellement un profil de candidat déjà structuré.
    """
    mock_candidates.append(cv)
    return {"message": "Candidate CV added successfully", "candidate": cv}

@router.post("/upload")
async def upload_cv(file: UploadFile = File(...)):
    """
    Endpoint pour uploader un CV PDF.
    Le fichier est analysé par cv_parser.py pour extraire les données.
    """
    file_bytes = await file.read()
    candidate = parse_cv_pdf(file_bytes, filename=file.filename)
    mock_candidates.append(candidate)
    return {"message": "CV uploaded and parsed successfully", "candidate": candidate}

@router.get("/")
def list_candidates():
    """
    Liste tous les candidats enregistrés.
    """
    return mock_candidates