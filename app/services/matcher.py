"""
Moteur de matching hybride (NLP + Sémantique).
Compare les exigences d'un poste (ParsedJobProfile) avec les preuves d'un candidat (ParsedCandidateProfile).
"""
import uuid
import re
from typing import List, Dict, Optional
try:
    from sentence_transformers import SentenceTransformer, util
    _EMBEDDING_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
except ImportError:
    _EMBEDDING_MODEL = None

from app.models.schemas import (
    ParsedJobProfile, 
    ParsedCandidateProfile, 
    RequirementMatchResult, 
    CandidateEvidenceItem,
    EnhancedScreeningResult,
    JobRequirementItem
)

DEGREE_RANK = {
    "Bac": 1, "Bts": 2, "Dut": 2, "Deust": 2,
    "Licence": 3, "Bachelor": 3, "M1": 3, "L3": 3,
    "Master": 4, "Ingénieur": 4, "Engineer": 4, "M2": 4,
    "Doctorat": 5, "Phd": 5
}

def calculate_semantic_similarity(text1: str, text2: str) -> float:
    """
    Calcule la similarité cosinus entre deux textes via embeddings.
    """
    if not _EMBEDDING_MODEL or not text1 or not text2:
        return 0.0
    
    emb1 = _EMBEDDING_MODEL.encode(text1, convert_to_tensor=True)
    emb2 = _EMBEDDING_MODEL.encode(text2, convert_to_tensor=True)
    
    return float(util.cos_sim(emb1, emb2)[0][0])

def match_requirement(requirement: JobRequirementItem, profile: ParsedCandidateProfile) -> RequirementMatchResult:
    """
    Analyse une exigence spécifique par rapport à l'ensemble du profil candidat.
    Pipeline de recherche en 3 étapes (du plus précis au plus général) :
      1. Mot-clé exact dans entités normalisées (SKILL_MAP)
      2. Mot-clé exact dans le texte brut des sections CV (keyword search)
      3. Similarité sémantique via embeddings
    """
    best_score = 0.0
    matching_evidence = []
    match_type = "missing"
    reasoning = ""

    req_label = requirement.label
    req_label_lower = req_label.lower()

    # ── Étape 1 : Exact match via entités normalisées ────────────────────
    for ev in profile.evidence:
        if any(req_label_lower == ent.lower() for ent in ev.normalized_entities):
            match_type = "exact"
            best_score = 1.0
            matching_evidence = [ev]
            reasoning = f"Correspondance exacte (entités normalisées) dans la section '{ev.source_section}'."
            break

    # ── Étape 2 : Keyword search dans le texte brut ──────────────────────
    # On cherche le label du job directement comme mot-clé dans le texte du CV.
    # Cette étape est indépendante du SKILL_MAP — elle fonctionne pour TOUT mot-clé extrait du JD.
    if match_type != "exact":
        for ev in profile.evidence:
            text_lower = ev.original_text.lower()
            # Recherche par correspondance de mot entier (\b) pour éviter les faux positifs
            if re.search(r"\b" + re.escape(req_label_lower) + r"\b", text_lower):
                match_type = "exact"
                best_score = 1.0
                matching_evidence = [ev]
                reasoning = f"Mot-clé '{req_label}' trouvé directement dans la section '{ev.source_section}' du CV."
                break

    # ── Étape 3 : Similarité sémantique (fallback) ───────────────────────
    if match_type != "exact":
        for ev in profile.evidence:
            sim = calculate_semantic_similarity(req_label, ev.original_text)
            if sim > 0.4:
                if sim > best_score:
                    best_score = sim
                    matching_evidence = [ev]

        if best_score >= 0.75:
            match_type = "semantic"
            reasoning = f"Compétence sémantiquement proche de '{req_label}' identifiée."
        elif best_score >= 0.4:
            match_type = "unclear"
            reasoning = f"Mention indirecte ou ambiguë de '{req_label}'."
        else:
            match_type = "missing"
            reasoning = f"Aucune preuve de '{req_label}' trouvée dans le CV."

    # Gestion spécifique de l'expérience et du diplôme si nécessaire
    # ── Spécificité : Diplôme (degree) ──────────────────────────────────
    # Pour les exigences de type 'degree', on applique une logique hiérarchique :
    # Si le candidat a un diplôme >= au niveau requis → exact match, même si le mot est différent.
    if requirement.type in ("degree", "education") and match_type != "exact":
        req_rank = None
        for deg, rank in DEGREE_RANK.items():
            if deg.lower() in req_label_lower:
                req_rank = rank
                break

        if req_rank is not None:
            # Cherche le diplôme du candidat dans les sections 'education' / 'formation'
            for ev in profile.evidence:
                if ev.source_section.lower() not in ("education", "formation", "studies", "diplome"):
                    continue
                ev_text = ev.original_text.lower()
                for deg, rank in DEGREE_RANK.items():
                    if deg.lower() in ev_text:
                        if rank >= req_rank:
                            match_type = "exact"
                            best_score = 1.0
                            matching_evidence = [ev]
                            reasoning = (
                                f"Diplôme candidat (niveau {rank}) ≥ exigence (niveau {req_rank})."
                            )
                        elif rank == req_rank - 1:
                            match_type = "unclear"
                            best_score = max(best_score, 0.5)
                            matching_evidence = [ev]
                            reasoning = f"Diplôme candidat (niveau {rank}) légèrement inférieur au requis (niveau {req_rank})."
                        break
                if match_type == "exact":
                    break

    # Statut final pour le chatbot
    status = "confirmed" if match_type == "exact" else "to_validate"
    if match_type == "missing":
        status = "to_validate" if requirement.importance in ["high", "critical"] else "rejected"

    return RequirementMatchResult(
        requirement_id=requirement.requirement_id,
        match_type=match_type,
        score=round(best_score, 2),
        found_evidence=matching_evidence,
        reasoning=reasoning,
        status=status
    )

def match_job_to_candidate(job: ParsedJobProfile, candidate: ParsedCandidateProfile) -> EnhancedScreeningResult:
    """
    Fonction principale : Effectue le matching requirement par requirement.
    """
    match_results = []
    total_score = 0.0
    
    if not job.requirements:
        return EnhancedScreeningResult(
            candidate_id=candidate.candidate_id,
            job_id=job.job_id,
            overall_score=0.0,
            summary="Aucune exigence extraite du poste pour le matching.",
            status="review"
        )
    
    for req in job.requirements:
        res = match_requirement(req, candidate)
        match_results.append(res)
        
        # Calcul du score pondéré simplifié
        # Importance weights: critical=1.5, high=1.2, medium=1.0, low=0.5
        weight_map = {"critical": 1.5, "high": 1.2, "medium": 1.0, "low": 0.5}
        w = weight_map.get(req.importance, 1.0)
        total_score += res.score * w
        
    max_possible_score = sum(weight_map.get(req.importance, 1.0) for req in job.requirements)
    final_score = (total_score / max_possible_score) * 100 if max_possible_score > 0 else 0
    
    # Résumé intelligent
    unclear_count = sum(1 for r in match_results if r.match_type == "unclear")
    missing_critical = sum(1 for i, r in enumerate(match_results) if r.match_type == "missing" and job.requirements[i].importance == "critical")
    
    summary = f"Matching de {len(job.requirements)} critères. "
    if missing_critical > 0:
        summary += f"Attention : {missing_critical} critère(s) critique(s) manquant(s). "
    if unclear_count > 0:
        summary += f"{unclear_count} point(s) d'ambiguïté à lever par le chatbot."
    
    # Statut
    if final_score >= 80 and missing_critical == 0:
        status = "shortlisted"
    elif final_score >= 40:
        status = "potential"
    else:
        status = "rejected"
        
    return EnhancedScreeningResult(
        candidate_id=candidate.candidate_id,
        job_id=job.job_id,
        overall_score=round(final_score, 2),
        requirement_matches=match_results,
        summary=summary,
        status=status
    )