# AI Recruitment Assistant : Requirement-Driven Candidate Filtering System

Ce projet est un système intelligent de présélection de candidatures assisté par l'Intelligence Artificielle (NLP & LLM). Il permet d'automatiser le filtrage initial des CVs puis d'affiner l'évaluation du candidat via un chatbot interactif ciblé sur les points d'ombre de son profil.

---

## Architecture "Requirement-Driven" (Logique Métier)

Le framework métier repose sur le paradigme **Requirement-Driven** (piloté par les exigences). Au lieu de comparer bêtement un texte global à un autre, le système découpe l'offre d'emploi en sous-exigences atomiques (skills, diplômes, expérience) et tente de trouver des **preuves (evidence)** dans le CV pour chaque exigence isolée.

### Le pipeline est divisé en 4 piliers principaux :

### 1. Extraction de l'Offre (Job Parser)
Lorsqu'une annonce brute est fournie au système, elle est envoyée à un LLM avec un prompt très strict.
- **Objectif** : Transformer un texte informel en objets `JobRequirementItem`.
- Chaque exigence possède un UUID, un Type (skill, degree, experience), un libellé, et une importance (low, medium, high, critical).
- *Fallback Local* : Si le LLM est indisponible, un moteur NLP hybride (avec spaCy et dictionnaires) extrait localement les compétences pour ne pas paralyser le système.

### 2. Extraction des CVs Candidats (CV Parser)
Le PDF est lu et paré via une approche algorithmique (expressions régulières + listes de mots).
- **Segmentation Contextuelle** : Le CV est découpé intelligemment en sections (Education, Experience, Skills, summary) grâce à des ancres.
- **Support Multi-CV (Batch Processing)** : Le système permet l'upload et le traitement simultané de plusieurs CVs.
- **Heuristiques Avancées** : L'extracteur d'expérience différencie les véritables années d'expérience des simples stages professionnels courts (< 1 an) pour éviter les biais.
- **Récolte des preuves (Evidence)** : Le parseur extrait des fragments de texte qui serviront de contexte pour justifier le score du candidat.

### 3. Moteur de Matching Hybride (Matcher)
C’est le cœur algorithmique du système. Il prend chaque exigence de l'offre et l'évalue contre les profils candidats via un processus en "entonnoir" :
1. **Exact Match (Dictionaries)** : Le libellé exact est-il dans les listes du CV ?
2. **Lexical Match (RegEx)** : Le mot-clé exact est-il mentionné quelque part dans le texte brut du CV ?
3. **Semantic Match (Sentence-Transformers)** : En dernier recours, l'IA utilise un modèle d'embedding NLP (MiniLM) pour chercher des phrases sémantiquement proches (ex: "Développement web backend" matche avec "Ingénierie de serveurs").
4. **Scoring Hierarchique** : Une exigence de "Licence" trouve un match "Parfait" si le candidat a un "Doctorat".

Le matcher attribue pour chaque exigence un **statut de clarté** : `exact`, `semantic`, `unclear`, ou `missing`. Lors d'une évaluation par lot, il génère une liste restreinte triée (Shortlisted, Potential, Rejected).

### 4. Chatbot et Analyse Ciblée (Interview Planner & Aggregator)
Le chatbot prend le relais là où le CV n'est pas suffisant, spécifiquement pour les candidats "Shortlisted" ou "Potential".
- **Génération du Plan d'Entretien** : Il identifie les exigences taguées comme `unclear` (floues) ou très critiques mais non maitrisées à 100%. Il crée une question pour combler ce vide.
- **Humanisation (LLM)** : La question technique est reformulée par le LLM pour être chaleureuse et contextuelle.
- **Analyse de Réponse** : Dès la réponse donnée, un évaluateur note la *Preuve* (Evidence), la *Pertinence* (Relevance), la *Clarté* (Clarity) et la *Stance* (assumée ou hésitante). 
- **Recalcul du Score** : Le score initial du candidat est ajusté à la hausse ou à la baisse.

---

## Persistance des Données (Base de données SQLite)

Le système utilise **SQLAlchemy** (ORM) branché sur une base **SQLite** (`candidates.db`), intégrée localement pour de hautes performances et zéro-config.
- Les CVs complets (`CandidateModel`), les offres (`JobModel`) et les sessions (`ChatbotSessionModel`) sont stockés via des colonnes `JSON`.
- Le système garantit qu'un candidat uploadé plusieurs fois possède un identifiant unique déterministe (évitant les doublons).
- La BDD assure que le Dashboard Streamlit peut recharger un processus même si le serveur redémarre.

---

## Stack Technique

- **Backend** : `FastAPI` (Python)
- **Base de données** : `SQLite` + `SQLAlchemy`
- **Frontend** : `Streamlit`
- **NLP Local** : `spaCy`, `regex`, `SentenceTransformers` (`all-MiniLM-L6-v2`)
- **API LLM** : Protocol OpenAI-compatible (utilisé via OpenRouter dans l'environnement actuel).

---

## Guide de Démarrage

### Lancement de l'API (Backend)
Dans le répertoire `candidate_filtering_system` :
```bash
python -m uvicorn app.main:app --reload
```
Le serveur sera disponible sur `http://localhost:8000` (docs sur `/docs`).

### Lancement de l'Interface UI (Frontend)
Dans un nouveau terminal :
```bash
python -m streamlit run app/frontend/streamlit_app.py
```
Le dashboard sera accessible sur `http://localhost:8501`.

---

## Déroulement du projet via l'interface Streamlit

L'interface utilisateur a été conçue pour refléter le flux de travail naturel d'un recruteur en 3 étapes (onglets) :

### 📋 Onglet 1 : Filtrage des CVs (Pipeline Initial)
1. **Offre d'emploi** : Collez un descriptif de poste RH classique. L'IA va le restructurer en grille d'évaluation structurée.
2. **Upload Multi-CVs** : Chargez simultanément plusieurs CVs PDF (Batch processing). L'extracteur les segmente et les stocke.
3. **Matching Global** : Cliquez sur "Lancer le filtrage". Le système évalue uniquement la *nouvelle* cohorte de CVs par rapport à l'offre et produit une liste restreinte triée par pertinence.

### 💬 Onglet 2 : Chatbot de Sélection
1. **Sélection du Candidat** : Choisissez l'un des candidats retenus (Shortlisted/Potential) issu de la première étape.
2. **Entretien Interactif** : Les zones grises détectées lors du matching déclenchent le Chatbot, qui posera des questions uniques orientées sur l'expérience du candidat.
3. **Analyse Continue** : L'IA évalue chaque réponse et met à jour le score du candidat en temps réel.

### 📊 Onglet 3 : Dashboard Recruteur (Validation)
1. **Vue de Synthèse** : Le recruteur accède au classement final mis à jour de la session de recrutement.
2. **Recommandations** : Les candidats ayant brillamment passé l'entretien chatbot sont mis en avant via une bannière "Recommandé pour entretien".
3. **Décision Finale** : Seuls les profils les plus pertinents et vérifiés sont transmis à l'entreprise pour un entretien avec un recruteur humain.
