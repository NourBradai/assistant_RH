"""
Routes pour la gestion des candidats et de leurs CVs.
Supporte l'extraction structurée (Sectioning + Evidence).
"""
# Existing imports (keep them as is)
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from app.models.schemas import CandidateCV, ParsedCandidateProfile
from app.services.cv_parser import parse_cv_to_structured_profile, estimate_experience_years
from app.database import get_db
from app.models.orm import CandidateModel

router = APIRouter()

# ... (existing routes unchanged) ...

@router.post("/recalc-experience")
def recalc_experience(db: Session = Depends(get_db)):
    """Recalcule l'expérience de tous les candidats déjà stockés.
    Utilise la logique mise à jour dans `estimate_experience_years`.
    Retourne le nombre de candidats mis à jour.
    """
    candidates = db.query(CandidateModel).all()
    updated = 0
    for candidate in candidates:
        # raw_text is stored in data['cv_info']['raw_text']
        cv_info = candidate.data.get("cv_info", {})
        raw = cv_info.get("raw_text", "")
        if not raw:
            continue
        new_years = estimate_experience_years(raw)
        # Update both locations where experience_years might be stored
        changed = False
        if candidate.data.get("experience_years") != new_years:
            candidate.data["experience_years"] = new_years
            changed = True
        
        if "cv_info" in candidate.data and candidate.data["cv_info"].get("experience_years") != new_years:
            candidate.data["cv_info"]["experience_years"] = new_years
            changed = True
            
        if changed:
            flag_modified(candidate, "data")
            updated += 1
    db.commit()
    return {"message": f"Recalculation done. {updated} candidates updated."}

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

@router.post("/upload-batch")
async def upload_cv_batch(files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    """
    Upload multiple CV PDFs at once.
    Returns a list of parsed profiles for batch processing.
    """
    results = []
    errors = []
    for file in files:
        try:
            file_bytes = await file.read()
            profile = parse_cv_to_structured_profile(file_bytes, filename=file.filename)
            # Check if candidate already exists (avoid duplicate)
            existing = db.query(CandidateModel).filter(CandidateModel.candidate_id == profile.candidate_id).first()
            if existing:
                existing.data = profile.model_dump()
                existing.name = profile.cv_info.name
            else:
                db_candidate = CandidateModel(
                    candidate_id=profile.candidate_id,
                    name=profile.cv_info.name,
                    data=profile.model_dump()
                )
                db.add(db_candidate)
            db.commit()
            results.append({
                "filename": file.filename,
                "candidate_id": profile.candidate_id,
                "name": profile.cv_info.name,
                "skills_count": len(profile.cv_info.skills),
                "experience_years": profile.cv_info.experience_years,
                "degree": profile.cv_info.degree,
                "profile": profile
            })
        except Exception as e:
            errors.append({"filename": file.filename, "error": str(e)})

    return {
        "message": f"{len(results)} CV(s) traité(s) avec succès, {len(errors)} erreur(s).",
        "profiles": results,
        "errors": errors
    }

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