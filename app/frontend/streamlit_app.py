import requests
import streamlit as st
from typing import Any

# =========================
# CONFIG
# =========================
BACKEND_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="AI Recruitment Assistant",
    page_icon="📄",
    layout="wide"
)

# =========================
# SESSION STATE INIT
# =========================
default_state = {
    "job_response": None,
    "candidate_response": None,
    "screening_response": None,
    "chatbot_start_response": None,
    "chatbot_final_response": None,
    "current_question": None,
    "job_id": "",
    "candidate_id": "",
    "session_id": "",
    "chat_history": [],
}

for key, value in default_state.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================
# HELPERS
# =========================
def handle_response(response: requests.Response) -> dict[str, Any]:
    """
    Gère proprement la réponse HTTP.
    """
    try:
        data = response.json()
    except Exception:
        data = {"detail": response.text}

    if response.status_code >= 400:
        raise Exception(data.get("detail", f"Erreur {response.status_code}"))

    return data


def api_post(endpoint: str, json_data: dict | None = None, files=None) -> dict[str, Any]:
    """
    Envoie une requête POST au backend.
    """
    url = f"{BACKEND_URL}{endpoint}"
    response = requests.post(url, json=json_data, files=files)
    return handle_response(response)


def api_get(endpoint: str, params: dict | None = None) -> dict[str, Any]:
    """
    Envoie une requête GET au backend.
    """
    url = f"{BACKEND_URL}{endpoint}"
    response = requests.get(url, params=params)
    return handle_response(response)


def show_json_block(title: str, data: Any):
    """
    Affiche joliment un bloc JSON.
    """
    st.subheader(title)
    st.json(data)


def show_success_message(message: str):
    st.success(message)


def show_error_message(error: Exception):
    st.error(str(error))


# =========================
# HEADER
# =========================
st.title("📄 AI Recruitment Assistant")
st.markdown(
    """
Cette interface permet de tester tout le pipeline :
1. création de l'offre,
2. upload du CV,
3. screening initial,
4. entretien chatbot,
5. recommandation finale.
"""
)

# =========================
# LAYOUT
# =========================
col_left, col_right = st.columns([1, 1])

# ============================================================
# LEFT COLUMN — JOB + CV + SCREENING
# ============================================================
with col_left:
    st.header("1) Offre d'emploi")

    with st.form("job_form"):
        job_id = st.text_input("Job ID", value="job_001")
        title = st.text_input("Titre du poste", value="Backend Python Developer")

        required_skills_raw = st.text_area(
            "Compétences obligatoires (séparées par des virgules)",
            value="Python, FastAPI, SQL"
        )
        preferred_skills_raw = st.text_area(
            "Compétences souhaitées (séparées par des virgules)",
            value="Docker, Git, Linux"
        )

        minimum_degree = st.text_input("Diplôme minimum", value="Licence")
        minimum_experience_years = st.number_input(
            "Expérience minimale (années)",
            min_value=0.0,
            value=2.0,
            step=0.5
        )

        required_languages_raw = st.text_input(
            "Langues requises (séparées par des virgules)",
            value="English"
        )
        preferred_languages_raw = st.text_input(
            "Langues souhaitées (séparées par des virgules)",
            value="French"
        )

        location = st.text_input("Localisation", value="Tunis")
        employment_type = st.text_input("Type de poste", value="Full-time")

        submit_job = st.form_submit_button("Créer l'offre")

    if submit_job:
        try:
            payload = {
                "job_id": job_id,
                "title": title,
                "required_skills": [x.strip() for x in required_skills_raw.split(",") if x.strip()],
                "preferred_skills": [x.strip() for x in preferred_skills_raw.split(",") if x.strip()],
                "minimum_degree": minimum_degree,
                "minimum_experience_years": minimum_experience_years,
                "required_languages": [x.strip() for x in required_languages_raw.split(",") if x.strip()],
                "preferred_languages": [x.strip() for x in preferred_languages_raw.split(",") if x.strip()],
                "location": location,
                "employment_type": employment_type,
                "weights": {
                    "required_skills": 40,
                    "preferred_skills": 15,
                    "experience": 20,
                    "degree": 10,
                    "languages": 10,
                    "projects_certifications": 5
                }
            }

            result = api_post("/jobs/", json_data=payload)
            st.session_state.job_response = result
            st.session_state.job_id = payload["job_id"]
            show_success_message("Offre créée avec succès.")
        except Exception as e:
            show_error_message(e)

    if st.session_state.job_response:
        show_json_block("Offre créée", st.session_state.job_response)

    st.divider()

    st.header("2) Upload du CV")

    uploaded_file = st.file_uploader("Choisir un CV PDF", type=["pdf"])

    if st.button("Uploader le CV", use_container_width=True):
        if not uploaded_file:
            st.warning("Veuillez choisir un PDF.")
        else:
            try:
                files = {
                    "file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")
                }
                result = api_post("/cvs/upload", files=files)

                st.session_state.candidate_response = result
                candidate = result.get("candidate", {})
                st.session_state.candidate_id = candidate.get("candidate_id", "")

                show_success_message("CV uploadé et parsé avec succès.")
            except Exception as e:
                show_error_message(e)

    if st.session_state.candidate_response:
        show_json_block("Candidat parsé", st.session_state.candidate_response)

    st.divider()

    st.header("3) Screening initial")

    if st.button("Lancer le screening", use_container_width=True):
        if not st.session_state.job_id or not st.session_state.candidate_id:
            st.warning("Il faut d'abord créer une offre et uploader un CV.")
        else:
            try:
                # FIX: Utiliser la route correcte avec path parameters
                endpoint = f"/screening/jobs/{st.session_state.job_id}/match/{st.session_state.candidate_id}"
                result = api_get(endpoint)
                st.session_state.screening_response = result
                show_success_message("Screening effectué avec succès.")
            except Exception as e:
                show_error_message(e)

    if st.session_state.screening_response:
        show_json_block("Résultat du screening", st.session_state.screening_response)

# ============================================================
# RIGHT COLUMN — CHATBOT + FINAL RESULT
# ============================================================
with col_right:
    st.header("4) Chatbot de présélection")

    if st.button("Démarrer le chatbot", use_container_width=True):
        if not st.session_state.job_id or not st.session_state.candidate_id:
            st.warning("Il faut d'abord créer une offre et uploader un CV.")
        else:
            try:
                payload = {
                    "job_id": st.session_state.job_id,
                    "candidate_id": st.session_state.candidate_id
                }
                result = api_post("/chatbot/start", json_data=payload)

                st.session_state.chatbot_start_response = result
                st.session_state.session_id = result.get("session_id", "")
                st.session_state.current_question = result.get("question", None)
                st.session_state.chat_history = []

                show_success_message("Session chatbot démarrée.")
            except Exception as e:
                show_error_message(e)

    if st.session_state.chatbot_start_response:
        show_json_block("Session chatbot", st.session_state.chatbot_start_response)

    st.divider()

    st.header("5) Répondre aux questions")

    session_id = st.session_state.session_id
    current_question = st.session_state.current_question

    if session_id and current_question:
        st.markdown("### Question actuelle")
        st.info(current_question.get("question_text", "Aucune question"))

        with st.form("answer_form", clear_on_submit=True):
            answer_text = st.text_area("Votre réponse")
            submit_answer = st.form_submit_button("Envoyer la réponse")

        if submit_answer:
            if not answer_text.strip():
                st.warning("Veuillez saisir une réponse.")
            else:
                try:
                    payload = {
                        "session_id": session_id,
                        "answer_text": answer_text
                    }

                    result = api_post("/chatbot/answer", json_data=payload)

                    last_turn = result.get("last_turn")
                    if last_turn:
                        st.session_state.chat_history.append(last_turn)

                    st.session_state.current_question = result.get("next_question", None)
                    
                    if result.get("status") == "completed":
                        st.session_state.chatbot_final_response = {
                            "session_id": result.get("session_id"),
                            "status": result.get("status"),
                            "chatbot_score": result.get("chatbot_score"),
                            "final_score": result.get("final_score"),
                            "final_decision": result.get("final_decision"),
                            "recruiter_summary": result.get("recruiter_summary"),
                            "last_turn": result.get("last_turn"),
                        }
                        show_success_message("Dernière réponse enregistrée. Session terminée.")
                    else:
                        show_success_message("Réponse enregistrée.")
                    
                    st.rerun()
                except Exception as e:
                    show_error_message(e)
    elif session_id and not current_question:
        st.info("Aucune question en attente ou session terminée.")
    else:
        st.caption("Le chatbot n'a pas encore été démarré.")

    if st.session_state.chat_history:
        st.markdown("### Historique des échanges")
        for idx, turn in enumerate(st.session_state.chat_history, start=1):
            st.markdown(f"**Q{idx}** : {turn['question']['question_text']}")
            st.write(f"**Réponse** : {turn.get('answer_text', '')}")
            analysis = turn.get("analysis")
            if analysis:
                st.caption(
                    f"Score réponse : {analysis.get('final_answer_score', 0)} | "
                    f"Pertinence : {analysis.get('relevance_score', 0)} | "
                    f"Preuve : {analysis.get('evidence_score', 0)} | "
                    f"Clarté : {analysis.get('clarity_score', 0)} | "
                    f"Position : {analysis.get('stance_score', 0)}"
                )
                st.caption(f"Justification : {analysis.get('justification', '')}")
            st.markdown("---")

    st.divider()

    st.header("6) Résultat final")

    if st.button("Récupérer le résultat final", use_container_width=True):
        if not st.session_state.session_id:
            st.warning("Aucune session chatbot active.")
        else:
            try:
                result = api_get(
                    "/chatbot/final",
                    params={"session_id": st.session_state.session_id}
                )
                st.session_state.chatbot_final_response = result
                show_success_message("Résultat final récupéré.")
            except Exception as e:
                show_error_message(e)

    if st.session_state.chatbot_final_response:
        result = st.session_state.chatbot_final_response

        st.subheader("Décision finale")
        final_decision = result.get("final_decision", "pending")
        final_score = result.get("final_score", 0)
        chatbot_score = result.get("chatbot_score", 0)

        if final_decision == "recommended":
            st.success(f"Décision : {final_decision}")
        elif final_decision == "review":
            st.warning(f"Décision : {final_decision}")
        else:
            st.error(f"Décision : {final_decision}")

        c1, c2 = st.columns(2)
        with c1:
            st.metric("Score chatbot", chatbot_score)
        with c2:
            st.metric("Score final", final_score)

        recruiter_summary = result.get("recruiter_summary")
        if recruiter_summary:
            st.markdown("### Résumé recruteur")
            st.write(recruiter_summary)

        show_json_block("Résultat final complet", result)