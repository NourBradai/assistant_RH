"""
Routes pour l'algorithme de screening.
Ce module utilise le service de scoring centralisé pour évaluer les candidats.
"""
from fastapi import APIRouter, HTTPException
from app.models.schemas import JobRequirement, CandidateCV, ScreeningResult
from app.services.scoring import calculate_screening_score
from app.database import mock_jobs, mock_candidates, mock_screening_results


router = APIRouter()

def save_screening_result(result: ScreeningResult):
    """
    Sauvegarde ou met à jour un résultat de screening dans la base simulée.
    """
    # On vide et on remplit la liste importée pour garder la référence globale
    for i, s in enumerate(mock_screening_results):
        if s.job_id == result.job_id and s.candidate_id == result.candidate_id:
            mock_screening_results.pop(i)
            break
    mock_screening_results.append(result)

@router.post("/test")
def simple_screening(job: JobRequirement, candidate: CandidateCV):
    """
    Endpoint de test pour le screening.
    """
    result = calculate_screening_score(job, candidate)
    save_screening_result(result)
    return result

@router.get("/jobs/{job_id}/match/{candidate_id}")
def match_candidate_to_job(job_id: str, candidate_id: str):
    """
    Route réelle de matching : trouve les objets par ID et calcule le score.
    """
    job = next((j for j in mock_jobs if j.job_id == job_id), None)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job avec l'ID {job_id} non trouvé")

    candidate = next((c for c in mock_candidates if c.candidate_id == candidate_id), None)
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidat avec l'ID {candidate_id} non trouvé")

    result = calculate_screening_score(job, candidate)
    save_screening_result(result)
    return result