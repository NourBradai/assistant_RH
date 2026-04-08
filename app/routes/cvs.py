"""
Routes pour la gestion des candidats et de leurs CVs.
Supporte l'extraction structurée (Sectioning + Evidence).
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from app.models.schemas import CandidateCV, ParsedCandidateProfile
from app.services.cv_parser import parse_cv_pdf, parse_cv_to_structured_profile
from app.database import get_db
from app.models.orm import CandidateModel

router = APIRouter()

@router.post("/")
def add_candidate(profile: ParsedCandidateProfile, db: Session = Depends(get_db)):
    """
    Ajoute un profil candidat déjà structuré.
    """
    db_candidate = CandidateModel(
        candidate_id=profile.candidate_id,
        name=profile.cv_info.name,
        data=profile.model_dump()
    )
    db.add(db_candidate)
    db.commit()
    return {"message": "Candidate profile added successfully", "candidate_id": profile.candidate_id}

@router.post("/upload")
async def upload_cv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Endpoint pour uploader un CV PDF.
    Utilise parse_cv_to_structured_profile pour extraire les preuves par section.
    """
    try:
        file_bytes = await file.read()
        profile = parse_cv_to_structured_profile(file_bytes, filename=file.filename)
        db_candidate = CandidateModel(
            candidate_id=profile.candidate_id,
            name=profile.cv_info.name,
            data=profile.model_dump()
        )
        db.add(db_candidate)
        db.commit()
        return {"message": "CV uploaded and profiled successfully", "profile": profile}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing CV: {str(e)}")

@router.get("/")
def list_candidates(db: Session = Depends(get_db)):
    """
    Liste tous les profils candidats.
    """
    candidates = db.query(CandidateModel).all()
    return [ParsedCandidateProfile(**c.data) for c in candidates]

@router.get("/{candidate_id}")
def get_candidate(candidate_id: str, db: Session = Depends(get_db)):
    """
    Récupère un candidat spécifique.
    """
    candidate = db.query(CandidateModel).filter(CandidateModel.candidate_id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return ParsedCandidateProfile(**candidate.data)