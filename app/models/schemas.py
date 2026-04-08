"""
Définition des schémas de données Pydantic utilisés pour la validation des requêtes et réponses API.
Ce fichier contient les modèles pour les jobs, les CVs, les résultats de screening et les sessions chatbot.
"""
from __future__ import annotations
from pydantic import BaseModel, Field, EmailStr
from typing import List, Dict, Optional, Any
from datetime import datetime


class JobWeights(BaseModel):
    """
    Définit les poids accordés à chaque critère lors du calcul du score final.
    Les valeurs par défaut totalisent 100%.
    """
    required_skills: float = Field(40, description="Poids des compétences obligatoires (%)")
    preferred_skills: float = Field(15, description="Poids des compétences secondaires (%)")
    experience: float = Field(20, description="Poids de l'expérience professionnelle (%)")
    degree: float = Field(10, description="Poids du niveau d'études (%)")
    languages: float = Field(10, description="Poids des langues maîtrisées (%)")
    projects_certifications: float = Field(5, description="Poids des projets et certifications (%)")


class JobRequirement(BaseModel):
    """
    Représente une offre d'emploi et ses critères de filtrage.
    """
    job_id: str
    title: str
    required_skills: List[str] = []
    preferred_skills: List[str] = []
    minimum_degree: Optional[str] = None
    minimum_experience_years: float = 0
    required_languages: List[str] = []
    preferred_languages: List[str] = []
    location: Optional[str] = None
    employment_type: Optional[str] = None
    weights: JobWeights = JobWeights()


class CandidateCV(BaseModel):
    """
    Représente les informations extraites d'un CV de candidat.
    """
    candidate_id: str
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    skills: List[str] = []
    degree: Optional[str] = None
    experience_years: float = 0
    languages: List[str] = []
    certifications: List[str] = []
    projects: List[str] = []
    raw_text: str  # Texte brut extrait du PDF pour référence


class ScreeningResult(BaseModel):
    """
    Résultat de l'analyse automatique d'un candidat pour un job spécifique.
    """
    candidate_id: str
    job_id: str
    initial_score: float
    matched_required_skills: List[str] = []
    missing_required_skills: List[str] = []
    matched_preferred_skills: List[str] = []
    strengths: List[str] = []
    weaknesses: List[str] = []
    status: str  # 'shortlisted' ou 'rejected'


class ChatQuestion(BaseModel):
    """
    Représente une question du chatbot, déjà prête à être posée au candidat.
    """
    question_id: str
    question_type: str
    question_text: str
    objective: str
    target_requirement_id: Optional[str] = None  # ID de l'exigence ciblée
    expected_signals: List[str] = Field(default_factory=list)
    weight: float = 1.0
    priority: str = "medium"


class QuestionAnalysis(BaseModel):
    """
    Représente l'analyse d'une réponse du candidat.
    Tous les scores sont sur 100.
    """
    relevance_score: float = 0.0
    evidence_score: float = 0.0
    clarity_score: float = 0.0
    stance_score: float = 0.0
    final_answer_score: float = 0.0
    updated_requirement_confidence: Optional[float] = None  # Nouveau score suggéré pour l'exigence cible
    justification: str = ""


class ChatTurn(BaseModel):
    """
    Représente un tour de conversation :
    une question + une réponse + l'analyse de cette réponse.
    """
    question: ChatQuestion
    answer_text: Optional[str] = None
    analysis: Optional[QuestionAnalysis] = None


class ChatbotSession(BaseModel):
    """
    Représente toute la session chatbot pour un candidat donné.
    """
    session_id: str
    job_id: str
    candidate_id: str
    initial_score: float = 0.0
    initial_screening: Optional[EnhancedScreeningResult] = None  # Résultats Détaillés
    questions: List[ChatQuestion] = Field(default_factory=list)
    turns: List[ChatTurn] = Field(default_factory=list)
    current_index: int = 0
    chatbot_score: float = 0.0
    final_score: float = 0.0
    final_decision: str = "pending"
    status: str = "active"


class StartChatbotRequest(BaseModel):
    """
    Requête pour démarrer une session chatbot.
    """
    job_id: str
    candidate_id: str


class SubmitAnswerRequest(BaseModel):
    """
    Requête pour soumettre une réponse à la question courante.
    """
    session_id: str
    answer_text: str


# --- Nouveaux modèles pour l'Approche "Requirement-Driven" ---

class JobRequirementItem(BaseModel):
    """
    Représente une exigence atomique extraite d'une offre d'emploi.
    """
    requirement_id: str
    type: str  # 'skill', 'experience', 'degree', 'language', 'seniority', 'constraint'
    label: str  # ex: "FastAPI"
    importance: str = "medium"  # 'low', 'medium', 'high', 'critical'
    required_level: Optional[str] = None  # ex: "practical", "expert"
    description: Optional[str] = None  # description textuelle du besoin
    category: Optional[str] = None  # ex: "backend_framework"


class ParsedJobProfile(BaseModel):
    """
    Profil structuré complet d'une offre d'emploi après analyse NLP/LLM.
    """
    job_id: str
    title: str
    requirements: List[JobRequirementItem] = []
    raw_text: str


class CandidateEvidenceItem(BaseModel):
    """
    Une preuve trouvée dans le CV pour une ou plusieurs exigences.
    """
    evidence_id: str
    source_section: str  # 'experience', 'education', 'projects', 'summary', 'skills'
    original_text: str
    normalized_entities: List[str] = []
    confidence_score: float = 1.0


class ParsedCandidateProfile(BaseModel):
    """
    Profil complet du candidat avec preuves structurées.
    """
    candidate_id: str
    cv_info: CandidateCV
    evidence: List[CandidateEvidenceItem] = []
    sections: Dict[str, str] = {}  # texte brut par section


class RequirementMatchResult(BaseModel):
    """
    Résultat du matching pour une exigence spécifique.
    """
    requirement_id: str
    match_type: str  # 'exact', 'semantic', 'unclear', 'missing', 'contradicted'
    score: float = 0.0
    found_evidence: List[CandidateEvidenceItem] = []
    reasoning: str = ""
    status: str = "pending"  # 'confirmed', 'rejected', 'to_validate' (via chatbot)


class EnhancedScreeningResult(BaseModel):
    """
    Résultat de screening enrichi basé sur l'analyse par exigences.
    """
    candidate_id: str
    job_id: str
    overall_score: float
    requirement_matches: List[RequirementMatchResult] = []
    summary: str
    status: str  # 'shortlisted', 'potential', 'rejected'