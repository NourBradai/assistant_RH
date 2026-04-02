"""
API principale pour le Système de Filtrage Automatique des Candidats.
Ce fichier initialise l'application FastAPI et enregistre tous les routeurs (Jobs, CVs, Screening, Chatbot).
"""
import os
from fastapi import FastAPI
from dotenv import load_dotenv

# Charger les variables d'environnement depuis le fichier .env (avec override pour refléter les changements)
base_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(base_dir, "..", ".env")
load_dotenv(dotenv_path=env_path, override=True)
print(f"--- SERVER STARTUP --- MODE: {os.getenv('LLM_MODE')} | MODEL: {os.getenv('LLM_MODEL')}")
from app.routes.jobs import router as jobs_router
from app.routes.cvs import router as cvs_router
from app.routes.screening import router as screening_router
from app.routes.chatbot import router as chatbot_router

# Configuration de l'application FastAPI
app = FastAPI(
    title="Candidate Filtering System",
    description="Système automatique de filtrage des candidatures avec extraction PDF et chatbot interactif.",
    version="1.0.0"
)

# Inclusion des routes par thématique
app.include_router(jobs_router, prefix="/jobs", tags=["Gestion des Jobs"])
app.include_router(cvs_router, prefix="/cvs", tags=["Gestion des CVs"])
app.include_router(screening_router, prefix="/screening", tags=["Algorithme de Scoring"])
app.include_router(chatbot_router, prefix="/chatbot", tags=["Assistant Chatbot"])


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """
    Route pour éviter l'erreur 404 du favicon dans les logs du navigateur.
    """
    return {"message": "No favicon"}

@app.get("/")
def root():
    """
    Point d'entrée racine de l'API. Utilisé pour vérifier si le serveur fonctionne.
    """
    return {"message": "Candidate Filtering System API is running"}