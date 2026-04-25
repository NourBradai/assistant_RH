"""
AI Recruitment Assistant — Frontend Streamlit
3 onglets : Pipeline de Filtrage | Chatbot | Dashboard Recruteur
"""
import requests
import streamlit as st

BACKEND_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="AI Recruitment Assistant", page_icon="🤖", layout="wide", initial_sidebar_state="collapsed")

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
    .candidate-card { background:#fff; border:1px solid #E5E7EB; border-radius:12px;
                      padding:16px; margin:8px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
    .status-shortlisted { color:#10B981; font-weight:700; }
    .status-potential { color:#F59E0B; font-weight:700; }
    .status-rejected { color:#EF4444; font-weight:700; }
    .recommended-banner { background:linear-gradient(135deg,#10B981,#059669); color:white;
                          border-radius:12px; padding:16px; text-align:center; margin:8px 0; }
</style>
""", unsafe_allow_html=True)

# ── SESSION STATE ──
defaults = {
    "job_profile": None, "candidate_profile": None, "screening_result": None,
    "chatbot_session": None, "current_question": None, "chat_history": [],
    "job_id": "", "candidate_id": "", "session_id": "",
    "batch_results": None, "uploaded_candidates": [],
    "chatbot_final": None, "batch_match_results": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── API HELPERS ──
def handle(r):
    try:
        data = r.json()
    except Exception:
        data = {"detail": r.text}
    if r.status_code >= 400:
        raise Exception(data.get("detail", f"HTTP {r.status_code}"))
    return data

def post(endpoint, json_data=None, files=None):
    return handle(requests.post(f"{BACKEND_URL}{endpoint}", json=json_data, files=files))

def get(endpoint, params=None):
    return handle(requests.get(f"{BACKEND_URL}{endpoint}", params=params))

# ── UI COMPONENTS ──
def importance_badge(importance):
    classes = {"critical": "imp-critical", "high": "imp-high", "medium": "imp-medium", "low": "imp-low"}
    icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}
    return f'<span class="{classes.get(importance, "")}">{icons.get(importance, "")} {importance.upper()}</span>'

def render_requirement_card(req):
    label = req.get("label", "?")
    req_type = req.get("type", "skill")
    importance = req.get("importance", "medium")
    level = req.get("required_level", "")
    category = req.get("category", "")
    desc = req.get("description", "")
    st.markdown(f"""<div class="req-card">
        <strong>{label}</strong> &nbsp;{importance_badge(importance)}
        &nbsp;<span style="color:#6B7280;font-size:0.8rem">{req_type}{' · ' + category if category else ''}</span><br>
        {('<small>' + level + '</small><br>') if level else ''}
        {('<small style="color:#6B7280">' + desc + '</small>') if desc else ''}
    </div>""", unsafe_allow_html=True)

def render_match_card(req_label, match):
    m_type = match.get("match_type", "missing")
    score = match.get("score", 0)
    reason = match.get("reasoning", "")
    status = match.get("status", "pending")
    icons = {"exact": "✅", "semantic": "🟡", "unclear": "❓", "missing": "⛔"}
    labels = {"exact": "Correspondance exacte", "semantic": "Match sémantique",
              "unclear": "Ambigu", "missing": "Absent"}
    st.markdown(f"""<div class="req-card match-{m_type}">
        <strong>{icons.get(m_type,'?')} {req_label}</strong>
        &nbsp;<span class="score-pill">{int(score*100)}%</span>
        &nbsp;<span style="font-size:0.8rem;color:#6B7280">{labels.get(m_type,m_type)}</span><br>
        <small style="color:#6B7280">{reason}</small><br>
        <small><em>Statut : {status}</em></small>
    </div>""", unsafe_allow_html=True)

# ── HEADER ──
st.markdown('<p class="main-header">🤖 AI Recruitment Assistant</p>', unsafe_allow_html=True)
st.markdown("**Système de filtrage automatique des candidatures** — Filtrage CV → Chatbot → Validation recruteur")
st.divider()

# ══════════════════════════════════════════════════════════════
# 3 ONGLETS PRINCIPAUX
# ══════════════════════════════════════════════════════════════
tab1, tab2, tab3 = st.tabs(["📋 1. Filtrage des CVs", "💬 2. Chatbot de Sélection", "📊 3. Dashboard Recruteur"])

# ══════════════════════════════════════════════════════════════
# TAB 1 — PIPELINE DE FILTRAGE
# ══════════════════════════════════════════════════════════════
with tab1:
    col_job, col_cv = st.columns([1, 1])

    # ── LEFT: Job Parsing ──
    with col_job:
        st.markdown('<span class="section-badge">Étape 1</span>', unsafe_allow_html=True)
        st.subheader("Offre d'emploi → Parsing automatique")

        with st.expander("📝 Coller le texte de l'offre d'emploi", expanded=True):
            raw_job_text = st.text_area("Texte brut de l'offre", height=180,
                placeholder="Ex: Nous recherchons un Développeur Backend Senior maîtrisant FastAPI, Docker...",
                label_visibility="collapsed")
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
                        r = requests.post(f"{BACKEND_URL}/jobs/parse", params={"raw_text": raw_job_text})
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
                        st.success(f"✅ Offre chargée : **{profile.get('title', '?')}**")
                    except Exception as e:
                        st.error(f"Erreur : {str(e)}")
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

    # ── RIGHT: Multi-CV Upload ──
    with col_cv:
        st.markdown('<span class="section-badge">Étape 2</span>', unsafe_allow_html=True)
        st.subheader("Upload multiple de CVs")

        uploaded_files = st.file_uploader("Charger les CVs des candidats (PDF)", type=["pdf"],
                                           accept_multiple_files=True)

        if st.button("📄 Uploader et analyser les CVs", use_container_width=True):
            if not uploaded_files:
                st.warning("Choisissez au moins un PDF.")
            else:
                with st.spinner(f"Analyse de {len(uploaded_files)} CV(s) en cours..."):
                    try:
                        files_payload = [("files", (f.name, f.getvalue(), "application/pdf")) for f in uploaded_files]
                        r = requests.post(f"{BACKEND_URL}/cvs/upload-batch", files=files_payload)
                        result = handle(r)
                        st.session_state.uploaded_candidates = result.get("profiles", [])
                        n_ok = len(result.get("profiles", []))
                        n_err = len(result.get("errors", []))
                        st.success(f"✅ {n_ok} CV(s) analysé(s) avec succès" + (f", {n_err} erreur(s)" if n_err else ""))
                        for err in result.get("errors", []):
                            st.error(f"❌ {err['filename']} : {err['error']}")
                    except Exception as e:
                        st.error(str(e))

        if st.session_state.uploaded_candidates:
            st.markdown(f"**{len(st.session_state.uploaded_candidates)} candidat(s) chargé(s) :**")
            for c in st.session_state.uploaded_candidates:
                c1, c2, c3 = st.columns(3)
                c1.metric("Nom", c.get("name", "?"))
                c2.metric("Expérience", f"{c.get('experience_years', 0)} ans")
                c3.metric("Compétences", c.get("skills_count", 0))

    st.divider()

    # ── STEP 3: Batch Matching ──
    st.markdown('<span class="section-badge">Étape 3</span>', unsafe_allow_html=True)
    st.subheader("Filtrage initial — Comparaison de tous les CVs avec le poste")

    has_job = bool(st.session_state.job_id)
    has_candidates = len(st.session_state.uploaded_candidates) > 0

    match_btn = st.button("⚡ Lancer le filtrage de tous les candidats", use_container_width=True,
                          disabled=not (has_job and has_candidates),
                          help="Uploadez d'abord une offre et des CVs")

    if match_btn:
        with st.spinner("Matching sémantique en cours pour tous les candidats..."):
            try:
                candidate_ids = [c["candidate_id"] for c in st.session_state.uploaded_candidates]
                payload = {"candidate_ids": candidate_ids}
                r = requests.post(f"{BACKEND_URL}/screening/jobs/{st.session_state.job_id}/match-all", json=payload)
                result = handle(r)
                st.session_state.batch_match_results = result
                n_short = result.get("shortlisted", 0)
                n_pot = result.get("potential", 0)
                n_rej = result.get("rejected", 0)
                st.success(f"✅ Filtrage terminé — ✅ {n_short} retenu(s) | 🟡 {n_pot} potentiel(s) | ❌ {n_rej} rejeté(s)")
            except Exception as e:
                st.error(str(e))

    if st.session_state.batch_match_results:
        results = st.session_state.batch_match_results.get("results", [])
        st.markdown("### 📊 Liste restreinte des candidats (triée par score)")

        for i, r in enumerate(results):
            status = r.get("status", "?")
            score = r.get("overall_score", 0)
            icon = {"shortlisted": "✅", "potential": "🟡", "rejected": "❌"}.get(status, "?")
            color = {"shortlisted": "#10B981", "potential": "#F59E0B", "rejected": "#EF4444"}.get(status, "#6B7280")

            st.markdown(f"""<div class="candidate-card">
                <strong>{i+1}. {r.get('name', '?')}</strong> &nbsp;
                <span style="color:{color};font-weight:700">{icon} {status.upper()}</span> &nbsp;
                <span class="score-pill">{score:.1f}%</span><br>
                <small style="color:#6B7280">{r.get('summary', '')}</small>
            </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# TAB 2 — CHATBOT
# ══════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<span class="section-badge">Étape 4</span>', unsafe_allow_html=True)
    st.subheader("Chatbot de validation — Sélection des meilleurs candidats")
    st.caption("Sélectionnez un candidat de la liste restreinte pour commencer l'entretien chatbot.")

    col_chat_left, col_chat_right = st.columns([1, 1])

    with col_chat_left:
        # Candidate selector
        candidates_for_chat = []
        if st.session_state.batch_match_results:
            for r in st.session_state.batch_match_results.get("results", []):
                if r.get("status") in ("shortlisted", "potential"):
                    candidates_for_chat.append(r)

        if candidates_for_chat:
            options = [f"{c['name']} — {c['overall_score']:.1f}% ({c['status']})" for c in candidates_for_chat]
            selected_idx = st.selectbox("Choisir un candidat", range(len(options)), format_func=lambda i: options[i])
            selected_candidate = candidates_for_chat[selected_idx]
            st.session_state.candidate_id = selected_candidate["candidate_id"]

            # Also load the screening result for this candidate
            try:
                r = requests.get(f"{BACKEND_URL}/screening/jobs/{st.session_state.job_id}/match/{st.session_state.candidate_id}")
                st.session_state.screening_result = handle(r)
            except:
                pass

            st.markdown(f"**Candidat sélectionné** : {selected_candidate['name']}")
            st.markdown(f"**Score initial** : {selected_candidate['overall_score']:.1f}%")
        else:
            st.info("Aucun candidat éligible. Lancez d'abord le filtrage dans l'onglet 1.")

        st.divider()

        # Start chatbot
        has_screening = st.session_state.screening_result is not None
        start_btn = st.button("💬 Démarrer le chatbot", use_container_width=True, disabled=not has_screening,
                              help="Le screening initial doit être effectué avant de démarrer.")

        if start_btn:
            with st.spinner("Initialisation du chatbot..."):
                try:
                    payload = {"job_id": st.session_state.job_id, "candidate_id": st.session_state.candidate_id}
                    result = post("/chatbot/start", json_data=payload)
                    st.session_state.chatbot_session = result
                    st.session_state.session_id = result.get("session_id", "")
                    q = result.get("first_question") or result.get("question")
                    st.session_state.current_question = q
                    st.session_state.chat_history = []
                    st.session_state.chatbot_final = None
                    st.success(f"Session démarrée — {result.get('total_questions', '?')} question(s) ciblées")
                except Exception as e:
                    st.error(str(e))

    with col_chat_right:
        st.markdown("#### 💬 Conversation")
        session_id = st.session_state.session_id
        current_q = st.session_state.current_question

        if session_id and current_q:
            st.markdown(f'<div class="chat-bubble-bot">🤖 <strong>Question</strong><br>{current_q.get("question_text", "")}</div>',
                        unsafe_allow_html=True)

            target_req = current_q.get("target_requirement_id")
            req_labels = {r["requirement_id"]: r["label"] for r in (st.session_state.job_profile or {}).get("requirements", [])} if st.session_state.job_profile else {}
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
                            if current_q:
                                st.session_state.chat_history.append({"question": current_q, "answer_text": answer_text})
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

        # Chat history
        if st.session_state.chat_history:
            st.markdown("#### Historique")
            for i, turn in enumerate(st.session_state.chat_history, 1):
                q_text = turn.get("question", {}).get("question_text", "")
                a_text = turn.get("answer_text", "")
                st.markdown(
                    f'<div class="chat-bubble-bot"><strong>Q{i}.</strong> {q_text}</div>'
                    f'<div class="chat-bubble-user">✍️ {a_text}</div>',
                    unsafe_allow_html=True)

        # Final result for this candidate
        st.divider()
        st.markdown("#### Résultat de l'entretien")

        get_result_btn = st.button("📊 Voir le résultat", use_container_width=True, disabled=not session_id)
        if get_result_btn:
            try:
                result = get(f"/chatbot/status/{session_id}")
                st.session_state.chatbot_final = result
            except Exception as e:
                st.error(str(e))

        final = st.session_state.get("chatbot_final")
        if final:
            decision = final.get("final_decision", "pending")
            final_score = final.get("final_score", 0)
            chatbot_score = final.get("chatbot_score", 0)
            initial_score = final.get("initial_score", st.session_state.screening_result.get("overall_score", 0) if st.session_state.screening_result else 0)

            decision_colors = {"recommended": "success", "review": "warning", "rejected": "error", "pending": "info"}
            decision_icons = {"recommended": "🟢", "review": "🟡", "rejected": "🔴", "pending": "🔵"}
            getattr(st, decision_colors.get(decision, "info"))(f"{decision_icons.get(decision, '?')} Décision : **{decision.upper()}**")

            c1, c2, c3 = st.columns(3)
            c1.metric("Score Initial", f"{initial_score:.1f}%")
            c2.metric("Score Chatbot", f"{chatbot_score:.1f}%")
            c3.metric("Score Final", f"{final_score:.1f}%")


# ══════════════════════════════════════════════════════════════
# TAB 3 — DASHBOARD RECRUTEUR
# ══════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<span class="section-badge">Étape 5</span>', unsafe_allow_html=True)
    st.subheader("📊 Validation et transmission des meilleurs profils")
    st.caption("Vue finale pour le recruteur — Candidats classés et prêts pour entretien humain.")

    if not st.session_state.job_id:
        st.info("Commencez par analyser une offre d'emploi dans l'onglet 1.")
    else:
        refresh_btn = st.button("🔄 Actualiser les résultats", use_container_width=True)
        if refresh_btn or st.session_state.batch_match_results:
            try:
                candidate_ids = [c["candidate_id"] for c in st.session_state.uploaded_candidates]
                # Convert list to query params format: ?candidate_ids=id1&candidate_ids=id2
                query_params = "&".join([f"candidate_ids={cid}" for cid in candidate_ids])
                url = f"/screening/jobs/{st.session_state.job_id}/candidates?{query_params}"
                data = get(url)
                candidates = data.get("candidates", [])
                job_title = data.get("job_title", "?")

                st.markdown(f"### Poste : {job_title} (`{st.session_state.job_id}`)")

                if not candidates:
                    st.warning("Aucun candidat n'a encore été évalué pour ce poste.")
                else:
                    # Summary metrics
                    recommended = [c for c in candidates if c.get("chatbot", {}) and c["chatbot"].get("final_decision") == "recommended"]
                    shortlisted = [c for c in candidates if c["status"] == "shortlisted"]
                    potential = [c for c in candidates if c["status"] == "potential"]
                    rejected = [c for c in candidates if c["status"] == "rejected"]

                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Total candidats", len(candidates))
                    m2.metric("✅ Retenus", len(shortlisted))
                    m3.metric("🟡 Potentiels", len(potential))
                    m4.metric("❌ Rejetés", len(rejected))

                    st.divider()

                    # Recommended after chatbot
                    if recommended:
                        st.markdown("### 🏆 Candidats recommandés pour entretien recruteur")
                        for c in recommended:
                            cb = c["chatbot"]
                            st.markdown(f"""<div class="recommended-banner">
                                <h3 style="margin:0;color:white">🟢 {c['name']}</h3>
                                <p style="margin:4px 0;color:rgba(255,255,255,0.9)">Score final : {cb['final_score']:.1f}% | Décision : RECOMMANDÉ</p>
                                <p style="margin:0;color:rgba(255,255,255,0.8)">Ce candidat est validé et transmis au recruteur pour un entretien.</p>
                            </div>""", unsafe_allow_html=True)
                        st.divider()

                    # Full table
                    st.markdown("### 📋 Classement complet")
                    for i, c in enumerate(candidates):
                        status = c.get("status", "?")
                        score = c.get("overall_score", 0)
                        icon = {"shortlisted": "✅", "potential": "🟡", "rejected": "❌"}.get(status, "?")
                        color = {"shortlisted": "#10B981", "potential": "#F59E0B", "rejected": "#EF4444"}.get(status, "#6B7280")

                        chatbot_info = ""
                        cb = c.get("chatbot")
                        if cb:
                            cb_decision = cb.get("final_decision", "pending")
                            cb_icon = {"recommended": "🟢", "review": "🟡", "rejected": "🔴", "pending": "🔵"}.get(cb_decision, "?")
                            chatbot_info = f" | Chatbot: {cb_icon} {cb_decision.upper()} ({cb.get('final_score', 0):.1f}%)"

                        st.markdown(f"""<div class="candidate-card">
                            <strong>{i+1}. {c.get('name', '?')}</strong> &nbsp;
                            <span style="color:{color};font-weight:700">{icon} {status.upper()}</span> &nbsp;
                            <span class="score-pill">{score:.1f}%</span>
                            <span style="font-size:0.85rem;color:#6B7280">{chatbot_info}</span>
                        </div>""", unsafe_allow_html=True)

            except Exception as e:
                st.error(f"Erreur lors du chargement : {str(e)}")