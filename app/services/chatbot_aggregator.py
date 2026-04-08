"""
Agrégateur final de score (Screening + Chatbot).
Met à jour les résultats de matching par exigence en fonction des réponses fournies par le candidat.
"""
from typing import List, Optional
from app.models.schemas import ChatbotSession, EnhancedScreeningResult, RequirementMatchResult

def finalize_chatbot_session(session: ChatbotSession) -> ChatbotSession:
    """
    Calcule le score final en mettant à jour le screening initial 
    avec les preuves apportées durant le chatbot.
    """
    if not session.initial_screening:
        session.status = "completed"
        return session

    # Copie profonde pour ne pas altérer l'original si nécessaire
    screening: EnhancedScreeningResult = session.initial_screening
    
    # On crée une map des exigences pour un accès rapide
    req_matches = {res.requirement_id: res for res in screening.requirement_matches}
    
    total_chatbot_score = 0.0
    answered_turns = 0  # Tous les tours avec une analyse valide
    req_answered_turns = 0  # Spécifiquement ceux ciblant une exigence

    for turn in session.turns:
        if not turn.analysis:
            continue

        analysis = turn.analysis
        final_score = analysis.final_answer_score or 0.0
        total_chatbot_score += final_score
        answered_turns += 1

        # Mise à jour de l'exigence ciblée si applicable
        req_id = turn.question.target_requirement_id
        if req_id and req_id in req_matches:
            req_answered_turns += 1
            current_match = req_matches[req_id]

            # Confiance apportée par la réponse orale (0-100 → 0-1)
            # Fallback: si updated_requirement_confidence est absent ou 0, on utilise final_answer_score
            raw_conf = analysis.updated_requirement_confidence
            if raw_conf and raw_conf > 0:
                chatbot_conf = raw_conf / 100.0
            else:
                chatbot_conf = final_score / 100.0  # Fallback mode mock

            if chatbot_conf > current_match.score:
                current_match.score = round(chatbot_conf, 2)
                current_match.reasoning += " [Confirmé par chatbot]"

            if chatbot_conf >= 0.8:
                current_match.match_type = "exact"
                current_match.status = "confirmed"

    # Score chatbot = moyenne pondérée sur toutes les réponses fournies
    session.chatbot_score = round(total_chatbot_score / answered_turns, 2) if answered_turns > 0 else 0.0

    # Score global = moyenne des scores de chaque exigence (mis à jour)
    n_reqs = len(screening.requirement_matches)
    final_overall_score = (sum(r.score for r in screening.requirement_matches) / n_reqs * 100) if n_reqs > 0 else 0.0
    session.final_score = round(final_overall_score, 2)
    session.initial_screening = screening # Mis à jour
    
    # Décision finale
    if session.final_score >= 75:
        session.final_decision = "recommended"
    elif session.final_score >= 50:
        session.final_decision = "review"
    else:
        session.final_decision = "rejected"
        
    session.status = "completed"
    return session

def build_recruiter_summary(session: ChatbotSession) -> str:
    """
    Génère un résumé textuel des points validés par le chatbot.
    """
    if not session.initial_screening:
        return "Pas de screening initial trouvé."
        
    confirmed = [r for r in session.initial_screening.requirement_matches if "[Confirmé par chatbot]" in r.reasoning]
    
    summary = f"Entretien terminé. Score final : {session.final_score}/100. "
    if confirmed:
        labels = [r.requirement_id for r in confirmed] # Faire mieux en prod avec les labels
        summary += f"Le candidat a réussi à clarifier/confirmer {len(confirmed)} point(s) d'ombre."
    else:
        summary += "Le chatbot n'a pas permis de lever d'ambiguïtés majeures."
        
    return summary