"""
Définition des schémas de données Pydantic utilisés pour la validation des requêtes et réponses API.
Ce fichier contient les modèles pour les jobs, les CVs, les résultats de screening et les sessions chatbot.
"""
from pydantic import BaseModel, Field, EmailStr
from typing import List, Dict, Optional


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


class ChatbotSession(BaseModel):
    """
    Gère l'état d'un entretien interactif via chatbot.
    """
    candidate_id: str
    job_id: str
    questions: List[str] = []
    answers: List[str] = []
    chatbot_score: float = 0
    final_score: float = 0
    final_decision: str = "pending"