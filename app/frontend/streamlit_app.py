"""
AI Recruitment Assistant — Frontend Streamlit
Architecture : Requirement-Driven NLP/LLM Matching Engine
"""
import requests
import streamlit as st
from typing import Any

BACKEND_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="AI Recruitment Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CSS CUSTOM ---
st.markdown("""
<style>
    .main-header { font-size: 2.2rem; font-weight: 800; color: #4F46E5; }
    .section-badge { display:inline-block; background:#EEF2FF; color:#4F46E5;
                     border-radius:8px; padding:2px 10px; font-size:0.85rem;
                     font-weight:600; margin-bottom:8px; }
    .req-card { background:#F9FAFB; border-left:4px solid #4F46E5;
                border-radius:8px; padding:10px 16px; margin:6px 0; }
    .match-exact  { border-left-color:#10B981; }
    .match-semantic { border-left-color:#F59E0B; }
    .match-unclear  { border-left-color:#EF4444; }
    .match-missing  { border-left-color:#6B7280; }
    .imp-critical { color:#DC2626; font-weight:700; }
    .imp-high     { color:#EA580C; font-weight:600; }
    .imp-medium   { color:#CA8A04; }
    .imp-low      { color:#6B7280; }
    .score-pill   { display:inline-block; background:#4F46E5; color:#fff;
                    border-radius:999px; padding:2px 12px; font-size:0.8rem; }
    .chat-bubble-bot  { background:#EEF2FF; border-radius:12px 12px 12px 2px;
                         padding:10px 16px; margin-bottom:8px; }
    .chat-bubble-user { background:#E0F2FE; border-radius:12px 12px 2px 12px;
                         padding:10px 16px; margin-bottom:8px; text-align:right; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# SESSION STATE
# ──────────────────────────────────────────────────────────────
defaults = {
    "job_profile": None,      # ParsedJobProfile dict
    "candidate_profile": None, # ParsedCandidateProfile dict
    "screening_result": None,  # EnhancedScreeningResult dict
    "chatbot_session": None,
    "current_question": None,
    "chat_history": [],
    "job_id": "",
    "candidate_id": "",
    "session_id": "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ──────────────────────────────────────────────────────────────
# API HELPERS
# ──────────────────────────────────────────────────────────────
def handle(r: requests.Response) -> dict:
    try:
        data = r.json()
    except Exception:
        data = {"detail": r.text}
    if r.status_code >= 400:
        raise Exception(data.get("detail", f"HTTP {r.status_code}"))
    return data

def post(endpoint, json_data=None, files=None) -> dict:
    return handle(requests.post(f"{BACKEND_URL}{endpoint}", json=json_data, files=files))

def get(endpoint, params=None) -> dict:
    return handle(requests.get(f"{BACKEND_URL}{endpoint}", params=params))


# ──────────────────────────────────────────────────────────────
# COMPOSANTS UI
# ──────────────────────────────────────────────────────────────
def importance_badge(importance: str) -> str:
    classes = {"critical": "imp-critical", "high": "imp-high",
               "medium": "imp-medium", "low": "imp-low"}
    icons   = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}
    return f'<span class="{classes.get(importance, "")}"> {icons.get(importance, "")} {importance.upper()}</span>'

def render_requirement_card(req: dict):
    label     = req.get("label", "?")
    req_type  = req.get("type", "skill")
    importance = req.get("importance", "medium")
    level     = req.get("required_level", "")
    category  = req.get("category", "")
    desc      = req.get("description", "")
    st.markdown(
        f"""<div class="req-card">
            <strong>{label}</strong>
            &nbsp;{importance_badge(importance)}
            &nbsp;<span style="color:#6B7280;font-size:0.8rem">{req_type}{' · ' + category if category else ''}</span><br>
            {('<small>' + level + '</small><br>') if level else ''}
            {('<small style="color:#6B7280">' + desc + '</small>') if desc else ''}
        </div>""",
        unsafe_allow_html=True
    )

def render_match_card(req_label: str, match: dict):
    m_type  = match.get("match_type", "missing")
    score   = match.get("score", 0)
    reason  = match.get("reasoning", "")
    status  = match.get("status", "pending")

    icons  = {"exact": "✅", "semantic": "🟡", "unclear": "❓", "missing": "⛔"}
    labels = {"exact": "Correspondance exacte", "semantic": "Match sémantique",
              "unclear": "Ambigu", "missing": "Absent"}

    st.markdown(
        f"""<div class="req-card match-{m_type}">
            <strong>{icons.get(m_type,'?')} {req_label}</strong>
            &nbsp;<span class="score-pill">{int(score*100)}%</span>
            &nbsp;<span style="font-size:0.8rem;color:#6B7280">{labels.get(m_type,m_type)}</span><br>
            <small style="color:#6B7280">{reason}</small><br>
            <small><em>Statut : {status}</em></small>
        </div>""",
        unsafe_allow_html=True
    )


# ──────────────────────────────────────────────────────────────
# HEADER
# ──────────────────────────────────────────────────────────────
st.markdown('<p class="main-header">🤖 AI Recruitment Assistant</p>', unsafe_allow_html=True)
st.markdown("**Moteur de sélection piloté par les exigences** — Analyse intelligente NLP/LLM")
st.divider()

# ──────────────────────────────────────────────────────────────
# LAYOUT PRINCIPAL
# ──────────────────────────────────────────────────────────────
col_left, col_right = st.columns([1, 1])

# ══════════════════════════════════════════════════════════════
# COLONNE GAUCHE — Job / CV / Screening
# ══════════════════════════════════════════════════════════════
with col_left:

    # ── STEP 1: Job Parser ──
    st.markdown('<span class="section-badge">Étape 1</span>', unsafe_allow_html=True)
    st.subheader("Offre d'emploi → Parsing automatique")

    with st.expander("📝 Coller le texte de l'offre d'emploi", expanded=True):
        raw_job_text = st.text_area(
            "Texte brut de l'offre",
            height=180,
            placeholder="Ex: Nous recherchons un Développeur Backend Senior maîtrisant FastAPI, Docker...",
            label_visibility="collapsed"
        )
        col_jid, col_jbtn = st.columns([1, 1])
        with col_jid:
            job_id_input = st.text_input("Job ID (optionnel)", placeholder="job_001")
        with col_jbtn:
            st.write("")
            parse_job_btn = st.button("🔍 Analyser ou Charger", use_container_width=True)

    if parse_job_btn:
        if raw_job_text.strip():
            with st.spinner("Extraction des exigences en cours..."):
                try:
                    # On appelle POST /jobs/parse avec le texte brut via un query param
                    r = requests.post(
                        f"{BACKEND_URL}/jobs/parse",
                        params={"raw_text": raw_job_text}
                    )
                    result = handle(r)
                    profile = result.get("profile", result)
                    st.session_state.job_profile = profile
                    st.session_state.job_id = profile.get("job_id", job_id_input)
                    st.success(f"✅ Offre analysée : **{profile.get('title', '?')}**")
                except Exception as e:
                    st.error(str(e))
        elif job_id_input.strip():
            with st.spinner("Chargement de l'offre existante..."):
                try:
                    r = requests.get(f"{BACKEND_URL}/jobs/{job_id_input.strip()}")
                    profile = handle(r)
                    st.session_state.job_profile = profile
                    st.session_state.job_id = profile.get("job_id", job_id_input.strip())
                    st.success(f"✅ Offre chargée depuis la BDD : **{profile.get('title', '?')}**")
                except Exception as e:
                    st.error(f"Offre introuvable ou erreur : {str(e)}")
        else:
            st.warning("Veuillez coller le texte de l'offre ou entrer un Job ID existant.")

    if st.session_state.job_profile:
        profile = st.session_state.job_profile
        st.markdown(f"**Poste** : {profile.get('title', '?')} — `{profile.get('job_id', '?')}`")
        reqs = profile.get("requirements", [])
        if reqs:
            st.markdown(f"**{len(reqs)} exigences extraites** :")
            for req in reqs:
                render_requirement_card(req)
        else:
            st.info("Aucune exigence extraite (LLM non configuré — mode mock).")

    st.divider()

    # ── STEP 2: CV Upload ──
    st.markdown('<span class="section-badge">Étape 2</span>', unsafe_allow_html=True)
    st.subheader("CV du candidat → Profiling par sections")

    uploaded_file = st.file_uploader("Charger un CV (PDF)", type=["pdf"])

    if st.button("📄 Uploader et analyser le CV", use_container_width=True):
        if not uploaded_file:
            st.warning("Choisissez un PDF.")
        else:
            with st.spinner("Extraction du profil candidat..."):
                try:
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                    result = post("/cvs/upload", files=files)
                    profile = result.get("profile", result)
                    st.session_state.candidate_profile = profile
                    cv_info = profile.get("cv_info", profile.get("candidate", {}))
                    st.session_state.candidate_id = cv_info.get("candidate_id", profile.get("candidate_id", ""))
                    st.success(f"✅ CV analysé : **{cv_info.get('name', 'Candidat')}**")
                except Exception as e:
                    st.error(str(e))

    if st.session_state.candidate_profile:
        profile = st.session_state.candidate_profile
        cv = profile.get("cv_info", profile)
        c1, c2, c3 = st.columns(3)
        c1.metric("Expérience", f"{cv.get('experience_years', 0)} ans")
        c2.metric("Diplôme", cv.get("degree", "N/D"))
        c3.metric("Compétences", len(cv.get("skills", [])))

        with st.expander("🔍 Preuves extraites par section"):
            for ev in profile.get("evidence", []):
                section = ev.get("source_section", "?")
                entities = ", ".join(ev.get("normalized_entities", [])) or "Aucune entité"
                conf = ev.get("confidence_score", 0)
                st.markdown(f"**{section.upper()}** — Confiance {int(conf*100)}%")
                st.caption(ev.get("original_text", "")[:300])
                st.code(entities, language=None)

    st.divider()

    # ── STEP 3: Matching ──
    st.markdown('<span class="section-badge">Étape 3</span>', unsafe_allow_html=True)
    st.subheader("Matching par exigences")

    match_btn = st.button("⚡ Lancer le matching sémantique", use_container_width=True,
                          disabled=not (st.session_state.job_id and st.session_state.candidate_id))

    if match_btn:
        with st.spinner("Analyse sémantique en cours..."):
            try:
                result = get(f"/screening/jobs/{st.session_state.job_id}/match/{st.session_state.candidate_id}")
                st.session_state.screening_result = result
                st.success(f"✅ Score global : **{result.get('overall_score', 0)}%** — Statut : {result.get('status', '?')}")
            except Exception as e:
                st.error(str(e))

    if st.session_state.screening_result:
        sr = st.session_state.screening_result
        score = sr.get("overall_score", 0)

        # Barre de progression
        color = "#10B981" if score >= 75 else "#F59E0B" if score >= 40 else "#EF4444"
        st.markdown(
            f"""<div style="background:#F3F4F6;border-radius:8px;height:16px;margin-bottom:12px">
                <div style="background:{color};width:{score}%;height:100%;border-radius:8px"></div>
            </div><small style="color:{color};font-weight:600">Score : {score}%</small>""",
            unsafe_allow_html=True
        )

        st.caption(sr.get("summary", ""))

        st.markdown("**Détail par exigence :**")

        # Récupérer les labels des exigences depuis le profil job pour l'affichage
        req_labels = {
            r["requirement_id"]: r["label"]
            for r in (st.session_state.job_profile or {}).get("requirements", [])
        } if st.session_state.job_profile else {}

        for match in sr.get("requirement_matches", []):
            req_id = match.get("requirement_id", "?")
            label = req_labels.get(req_id, req_id)
            render_match_card(label, match)


# ══════════════════════════════════════════════════════════════
# COLONNE DROITE — Chatbot + Résultat Final
# ══════════════════════════════════════════════════════════════
with col_right:

    # ── STEP 4: Chatbot ──
    st.markdown('<span class="section-badge">Étape 4</span>', unsafe_allow_html=True)
    st.subheader("Chatbot de validation contextuel")

    has_screening = st.session_state.screening_result is not None
    start_btn = st.button(
        "💬 Démarrer le chatbot",
        use_container_width=True,
        disabled=not has_screening,
        help="Le screening initial doit être effectué avant de démarrer."
    )

    if start_btn:
        with st.spinner("Initialisation du chatbot..."):
            try:
                payload = {
                    "job_id": st.session_state.job_id,
                    "candidate_id": st.session_state.candidate_id
                }
                result = post("/chatbot/start", json_data=payload)
                st.session_state.chatbot_session = result
                st.session_state.session_id = result.get("session_id", "")
                
                # La première question peut être dans first_question ou question
                q = result.get("first_question") or result.get("question")
                st.session_state.current_question = q
                st.session_state.chat_history = []
                st.success(f"Session démarrée — {result.get('total_questions', '?')} question(s) ciblées")
            except Exception as e:
                st.error(str(e))

    if st.session_state.chatbot_session:
        s = st.session_state.chatbot_session
        nb_q = s.get("total_questions", "?")
        st.caption(f"Session `{st.session_state.session_id[:12]}...` — {nb_q} question(s)")

    st.divider()

    # ── STEP 5: Répondre ──
    st.markdown('<span class="section-badge">Étape 5</span>', unsafe_allow_html=True)
    st.subheader("Questions contextuelles")

    session_id = st.session_state.session_id
    current_q = st.session_state.current_question

    if session_id and current_q:
        # Afficher la question dans une bulle
        st.markdown(
            f'<div class="chat-bubble-bot">🤖 <strong>Question</strong><br>{current_q.get("question_text", "")}</div>',
            unsafe_allow_html=True
        )

        # Afficher la cible de la question si disponible
        target_req = current_q.get("target_requirement_id")
        req_labels = {
            r["requirement_id"]: r["label"]
            for r in (st.session_state.job_profile or {}).get("requirements", [])
        } if st.session_state.job_profile else {}
        if target_req and target_req in req_labels:
            st.caption(f"🎯 Cette question valide : **{req_labels[target_req]}**")

        with st.form("answer_form", clear_on_submit=True):
            answer_text = st.text_area("Votre réponse", height=80, label_visibility="collapsed",
                                       placeholder="Décrivez votre expérience en détail...")
            submit = st.form_submit_button("📤 Envoyer", use_container_width=True)

        if submit:
            if not answer_text.strip():
                st.warning("Réponse vide.")
            else:
                with st.spinner("Analyse de la réponse..."):
                    try:
                        payload = {"session_id": session_id, "answer_text": answer_text}
                        result = post("/chatbot/answer", json_data=payload)

                        # On stocke la réponse dans l'historique
                        if current_q:
                            st.session_state.chat_history.append({
                                "question": current_q,
                                "answer_text": answer_text
                            })

                        # Prochaine question ou fin
                        next_q = result.get("next_question")
                        st.session_state.current_question = next_q

                        if result.get("status") == "completed" or result.get("final_score") is not None:
                            st.session_state.chatbot_final = result
                            st.success("✅ Entretien terminé.")

                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    elif session_id and not current_q:
        st.info("✅ Toutes les questions ont été traitées.")
    else:
        st.caption("_Démarrez le chatbot pour commencer l'entretien._")

    # Historique des échanges
    if st.session_state.chat_history:
        st.markdown("#### Historique")
        for i, turn in enumerate(st.session_state.chat_history, 1):
            q_text = turn.get("question", {}).get("question_text", "")
            a_text = turn.get("answer_text", "")
            st.markdown(
                f'<div class="chat-bubble-bot"><strong>Q{i}.</strong> {q_text}</div>'
                f'<div class="chat-bubble-user">✍️ {a_text}</div>',
                unsafe_allow_html=True
            )

    st.divider()

    # ── STEP 6: Résultat Final ──
    st.markdown('<span class="section-badge">Étape 6</span>', unsafe_allow_html=True)
    st.subheader("Décision finale")

    get_result_btn = st.button("📊 Voir le résultat final", use_container_width=True,
                               disabled=not session_id)
    if get_result_btn:
        try:
            result = get(f"/chatbot/status/{session_id}")
            st.session_state.chatbot_final = result
        except Exception as e:
            st.error(str(e))

    final = getattr(st.session_state, "chatbot_final", None) or st.session_state.get("chatbot_final")

    if final:
        decision   = final.get("final_decision", "pending")
        final_score = final.get("final_score", 0)
        chatbot_score = final.get("chatbot_score", 0)
        initial_score = final.get("initial_score", st.session_state.screening_result.get("overall_score", 0) if st.session_state.screening_result else 0)

        decision_colors = {"recommended": "success", "review": "warning", "rejected": "error", "pending": "info"}
        decision_icons  = {"recommended": "🟢", "review": "🟡", "rejected": "🔴", "pending": "🔵"}
        getattr(st, decision_colors.get(decision, "info"))(
            f"{decision_icons.get(decision, '?')} Décision : **{decision.upper()}**"
        )

        c1, c2, c3 = st.columns(3)
        c1.metric("Score Initial", f"{initial_score:.1f}%")
        c2.metric("Score Chatbot", f"{chatbot_score:.1f}%")
        c3.metric("Score Final", f"{final_score:.1f}%", delta=f"+{final_score - initial_score:.1f}%" if final_score > initial_score else None)

        summary = final.get("summary")
        if not summary and final.get("initial_screening"):
            summary = final["initial_screening"].get("summary")
        if summary:
            st.info(f"📝 {summary}")

        with st.expander("Détail complet de la session"):
            st.json(final)