"""
Service de Scoring haut-niveau.
Ce module sert désormais de wrapper pour la logique de matching et de calcul de score 
centralisée dans matcher.py.
"""
from app.models.schemas import CandidateCV, JobRequirement, ScreeningResult
from app.services.matcher import compute_screening_result

def calculate_screening_score(job: JobRequirement, candidate: CandidateCV) -> ScreeningResult:
    """
    Orchestre le calcul du score de screening en appelant le moteur de matching.
    """
    return compute_screening_result(job, candidate)
