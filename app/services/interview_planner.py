"""
Générateur de plan d'entretien basé sur les exigences (Requirement-Driven).
Cible les zones d'ombre (Semantic, Unclear) identifiées par le Matcher.
"""
import uuid
from typing import List, Optional
from app.models.schemas import (
    ParsedJobProfile, 
    ParsedCandidateProfile, 
    EnhancedScreeningResult, 
    ChatQuestion,
    RequirementMatchResult,
    JobRequirementItem
)

def create_contextual_question(
    req: JobRequirementItem, 
    match_res: RequirementMatchResult
) -> ChatQuestion:
    """
    Crée une question adaptée au type de match trouvé.
    """
    question_text = ""
    objective = f"Valider l'exigence : {req.label}"
    expected_signals = [req.label.lower()]
    
    if match_res.match_type == "semantic":
        # On utilise les évidences proches pour poser la question
        evidence_labels = ", ".join([ent for ev in match_res.found_evidence for ent in ev.normalized_entities[:2]])
        question_text = (
            f"Votre profil montre une expérience avec {evidence_labels}. "
            f"Dans quelle mesure avez-vous pu appliquer ces compétences à des problématiques liées à {req.label} ?"
        )
    elif match_res.match_type == "unclear":
        question_text = (
            f"Pouvez-vous nous en dire plus sur votre expérience avec {req.label} ? "
            f"Nous n'avons pas trouvé de détails précis dans votre CV."
        )
    else: # Missing critical
        question_text = (
            f"Le poste requiert une maîtrise de {req.label}. "
            f"Avez-vous déjà travaillé avec cet outil ou un équivalent dans vos projets passés ?"
        )

    return ChatQuestion(
        question_id=f"q_{uuid.uuid4().hex[:6]}",
        question_type=req.type,
        question_text=question_text,
        objective=objective,
        target_requirement_id=req.requirement_id,
        expected_signals=expected_signals,
        weight=1.5 if req.importance == "critical" else 1.0,
        priority="high" if req.importance in ["critical", "high"] else "medium"
    )

def build_interview_plan(
    job: ParsedJobProfile,
    candidate: ParsedCandidateProfile,
    screening: EnhancedScreeningResult,
    max_questions: int = 5
) -> List[ChatQuestion]:
    """
    Construit un plan d'entretien ciblé sur les manques et ambiguïtés.
    """
    questions = []
    
    # On récupère les exigences nécessitant validation
    # Priorité : critical > high > medium
    requirements_dict = {req.requirement_id: req for req in job.requirements}
    
    results_to_validate = [r for r in screening.requirement_matches if r.status == "to_validate"]
    
    # Tri par importance de l'exigence liée
    results_to_validate.sort(
        key=lambda r: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(requirements_dict[r.requirement_id].importance, 4)
    )
    
    for res in results_to_validate:
        req = requirements_dict[res.requirement_id]
        questions.append(create_contextual_question(req, res))
        
        if len(questions) >= max_questions:
            break
            
    # Si on a trop peu de questions techniques, on peut ajouter une question de clôture/disponibilité
    if len(questions) < 3:
        questions.append(ChatQuestion(
            question_id="q_hr_avail",
            question_type="hr",
            question_text="Quelle serait votre date de disponibilité la plus proche pour débuter ?",
            objective="Vérifier la disponibilité réelle.",
            expected_signals=["disponible", "préavis", "immédiat"],
            weight=0.5,
            priority="low"
        ))
        
    return questions