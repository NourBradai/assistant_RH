"""
Service d'analyse et d'extraction des exigences d'une offre d'emploi.
Utilise principalement le LLM pour transformer du texte brut en profil structuré.
"""
import uuid
from typing import Dict, List
from app.models.schemas import ParsedJobProfile, JobRequirementItem
from app.services.llm_client import extract_job_requirements_with_llm

def parse_job_description(raw_text: str, job_id: str = None) -> ParsedJobProfile:
    """
    Extrait toutes les exigences d'une offre d'emploi.
    """
    if not job_id:
        job_id = f"job_{uuid.uuid4().hex[:8]}"
    
    # Appel au LLM pour l'extraction structurée
    extracted_data = extract_job_requirements_with_llm(raw_text)
    
    title = extracted_data.get("job_title", "Poste sans titre")
    requirements_data = extracted_data.get("requirements", [])
    
    requirements = []
    for req in requirements_data:
        requirements.append(JobRequirementItem(
            requirement_id=f"req_{uuid.uuid4().hex[:6]}",
            type=req.get("type", "skill"),
            label=req.get("label", "Unknown"),
            importance=req.get("importance", "medium"),
            required_level=req.get("required_level"),
            description=req.get("description"),
            category=req.get("category")
        ))
    
    return ParsedJobProfile(
        job_id=job_id,
        title=title,
        requirements=requirements,
        raw_text=raw_text
    )

def get_fallback_job_profile(raw_text: str) -> ParsedJobProfile:
    """
    Version de secours si le LLM échoue totalement.
    Tente une extraction basique par mots-clés (très limitée).
    """
    return ParsedJobProfile(
        job_id=f"job_fallback_{uuid.uuid4().hex[:4]}",
        title="Extraction Fallback",
        requirements=[
            JobRequirementItem(
                requirement_id="req_fallback_1",
                type="skill",
                label="Analyse manuelle requise",
                importance="high"
            )
        ],
        raw_text=raw_text
    )
