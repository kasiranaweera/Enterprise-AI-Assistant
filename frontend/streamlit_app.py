"""
Streamlit frontend for Northbridge Commercial Bank — Internal AI Assistant.

Dynamically adapts UI capabilities and navigation based on user role:
- Viewer: Chat, Search documents, View retrieved documents, Conversation history, Conversational memory
- Analyst: All above + Deep/RLM research, Python data analysis, MCP tools, Analytics
- Administrator: All above + Admin tools (Manage users, Manage roles/permissions, Manage knowledge base,
                 Upload documents, Delete documents, System config, System/audit logs)
"""
import json
import os
import requests
import streamlit as st

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Enterprise AI Assistant — Northbridge Bank",
    page_icon="🏦",
    layout="wide",
)

# ------------------------------------------------ Session State Management ----
if "token" not in st.session_state:
    st.session_state.token = None
    st.session_state.role = None
    st.session_state.username = None
if "sessions_messages" not in st.session_state:
    st.session_state.sessions_messages = {"session-1": []}
if "session_id" not in st.session_state:
    st.session_state.session_id = "session-1"

# ------------------------------------------------ Login Screen ----------------
if st.session_state.token is None:
    st.title("🏦 Northbridge Commercial Bank — Internal AI Assistant")
    st.subheader("Secure Employee Sign-In")
    st.caption("Role-Based Access Control (RBAC) Demonstration")

    col_login, col_matrix = st.columns([1, 1.2])

    with col_login:
        st.markdown("### 🔐 Credentials")
        with st.form("login_form"):
            username = st.text_input("Username", value="analyst1")
            password = st.text_input("Password", type="password", value="analyst123")
            submitted = st.form_submit_button("Sign In", use_container_width=True)

        if submitted:
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/auth/login",
                    json={"username": username, "password": password},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state.token = data["access_token"]
                    st.session_state.role = data["role"]
                    st.session_state.username = data["username"]
                    st.rerun()
                else:
                    detail = resp.json().get("detail", "Authentication failed")
                    st.error(f"Login failed: {detail}")
            except requests.RequestException as exc:
                st.error(f"Could not reach backend at {BACKEND_URL}: {exc}")

        st.info(
            "**Quick Demo Logins:**\n"
            "- 👤 `viewer1` / `viewer123` (Viewer: read-only access)\n"
            "- 📊 `analyst1` / `analyst123` (Analyst: RLM, analytics, MCP)\n"
            "- 🛡️ `admin1` / `admin123` (Administrator: full system control)"
        )

    with col_matrix:
        st.markdown("### 📋 Role Capability Matrix")
        st.markdown(
            """
| Action | Viewer | Analyst | Administrator |
| :--- | :---: | :---: | :---: |
| 💬 Chat with AI | ✅ | ✅ | ✅ |
| 🔎 Search documents | ✅ | ✅ | ✅ |
| 📄 View retrieved documents | ✅ | ✅ | ✅ |
| 📚 View conversation history | ✅ | ✅ | ✅ |
| 🧠 Use conversational memory | ✅ | ✅ | ✅ |
| 🔍 Advanced/RLM research | ❌ | ✅ | ✅ |
| 📊 Python data analysis | ❌ | ✅ | ✅ |
| 🔧 MCP tools | ❌ | ✅ | ✅ |
| 📈 Analytics | ❌ | ✅ | ✅ |
| 🛠️ Administrative tools | ❌ | ❌ | ✅ |
| 👥 Manage users | ❌ | ❌ | ✅ |
| 🔐 Manage roles/permissions | ❌ | ❌ | ✅ |
| 📚 Manage knowledge base | ❌ | ❌ | ✅ |
| ➕ Upload documents | ❌ | ❌ | ✅ |
| 🗑️ Delete documents | ❌ | ❌ | ✅ |
| ⚙️ System configuration | ❌ | ❌ | ✅ |
| 📋 View system/audit logs | ❌ | ❌ | ✅ |
            """
        )
    st.stop()

# ------------------------------------------------ Authenticated Header --------
auth_headers = {"Authorization": f"Bearer {st.session_state.token}"}
role = st.session_state.role
username = st.session_state.username

# Role badge styling
role_colors = {
    "viewer": "🔵 Viewer",
    "analyst": "🟣 Analyst",
    "administrator": "🟢 Administrator",
}
role_badge = role_colors.get(role, role.capitalize())

header_col1, header_col2 = st.columns([4, 1])
with header_col1:
    st.title("🏦 Northbridge Bank — AI Assistant")
    st.markdown(f"Signed in as **{username}** | Role: **{role_badge}** | Backend: `{BACKEND_URL}`")
with header_col2:
    st.write("")
    if st.button("🚪 Sign Out", use_container_width=True):
        st.session_state.token = None
        st.session_state.role = None
        st.session_state.username = None
        st.rerun()

# ------------------------------------------------ Sidebar Controls ------------
with st.sidebar:
    st.markdown(f"### 👤 {username}")
    st.markdown(f"**Permissions tier:** `{role}`")

    with st.expander("ℹ️ Active Role Permissions"):
        st.markdown(
            f"""
        **Role: {role.upper()}**
        - Chat & QA: ✅
        - Knowledge Search: ✅
        - View Retrieved Docs: ✅
        - Conversation History: ✅
        - Conversational Memory: ✅
        - Advanced RLM Research: {'✅' if role in ['analyst', 'administrator'] else '❌ (Requires Analyst+)'}
        - Python Data Analysis: {'✅' if role in ['analyst', 'administrator'] else '❌ (Requires Analyst+)'}
        - MCP Tools: {'✅' if role in ['analyst', 'administrator'] else '❌ (Requires Analyst+)'}
        - Analytics: {'✅' if role in ['analyst', 'administrator'] else '❌ (Requires Analyst+)'}
        - Admin Tools: {'✅' if role == 'administrator' else '❌ (Requires Admin)'}
        - Knowledge Base Edit: {'✅' if role == 'administrator' else '❌ (Requires Admin)'}
        """
        )

    st.divider()

    # 📚 View Conversation History & Session Switcher
    st.markdown("### 📚 Conversation Sessions")
    session_list = list(st.session_state.sessions_messages.keys())
    selected_session = st.selectbox(
        "Current Session",
        session_list,
        index=session_list.index(st.session_state.session_id) if st.session_state.session_id in session_list else 0,
    )
    if selected_session != st.session_state.session_id:
        st.session_state.session_id = selected_session
        st.rerun()

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("➕ New Session", use_container_width=True):
            new_id = f"session-{len(st.session_state.sessions_messages) + 1}"
            st.session_state.sessions_messages[new_id] = []
            st.session_state.session_id = new_id
            st.rerun()
    with col_s2:
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.sessions_messages[st.session_state.session_id] = []
            st.rerun()

    # 🧠 Use Conversational Memory
    st.divider()
    st.markdown("### 🧠 Conversational Memory")
    if st.button("Inspect Session Memory", use_container_width=True):
        try:
            mem_resp = requests.get(
                f"{BACKEND_URL}/chat/memory/{st.session_state.session_id}",
                headers=auth_headers,
                timeout=5,
            )
            if mem_resp.status_code == 200:
                mem_data = mem_resp.json()
                st.session_state.memory_inspect = mem_data
            else:
                st.warning("Could not fetch memory state.")
        except Exception as e:
            st.error(f"Memory check failed: {e}")

    if "memory_inspect" in st.session_state:
        mem = st.session_state.memory_inspect
        st.caption(f"Raw turns buffered: {mem.get('raw_turns_count', 0)}")
        if mem.get("running_summary"):
            st.markdown(f"**Running Summary:**\n_{mem['running_summary']}_")
        else:
            st.caption("No compaction summary yet (< 6 turns).")

    if st.button("Reset Memory Context", use_container_width=True):
        try:
            requests.delete(
                f"{BACKEND_URL}/chat/memory/{st.session_state.session_id}",
                headers=auth_headers,
                timeout=5,
            )
            st.session_state.pop("memory_inspect", None)
            st.success("Memory context cleared on backend.")
        except Exception as e:
            st.error(f"Failed to reset memory: {e}")

# Ensure active messages list exists
if st.session_state.session_id not in st.session_state.sessions_messages:
    st.session_state.sessions_messages[st.session_state.session_id] = []
current_messages = st.session_state.sessions_messages[st.session_state.session_id]

# ------------------------------------------------ Role-Based Tabs -------------
tab_names = ["💬 Chat with AI", "🔎 Search Documents"]
if role in ["analyst", "administrator"]:
    tab_names.extend(["📊 Python Analysis", "🔧 MCP Tools", "📈 Analytics"])
if role == "administrator":
    tab_names.append("🛠️ Admin Console")

tabs = st.tabs(tab_names)

# ==============================================================================
# TAB 1: 💬 Chat with AI
# ==============================================================================
with tabs[0]:
    chat_col, activity_col = st.columns([2, 1])

    with chat_col:
        st.subheader("💬 Assistant Chat")

        # Role-based feature banner
        deep_research = False
        if role in ["analyst", "administrator"]:
            deep_research = st.checkbox(
                "🔍 Advanced / RLM Research Mode (Recursive multi-batch synthesis & root cause analysis)",
                value=False,
                help="When enabled, decomposes broad questions into batches, executes recursive sub-agent passes, and aggregates root causes.",
            )
        else:
            st.caption("🔒 *Advanced / RLM Deep Research is available for Analyst & Administrator roles.*")

        def format_citations(text: str) -> str:
            import re
            def _clean_chip(match):
                raw_id = match.group(1)
                parts = raw_id.split("__")
                title = parts[-1].replace("-", " ").title() if len(parts) >= 5 else raw_id
                return f" `[📄 {title}]`"
            return re.sub(r"\[doc:([^\]]+)\]", _clean_chip, text)

        # Display history
        for msg in current_messages:
            with st.chat_message(msg["role"]):
                if msg["role"] == "assistant":
                    st.markdown(format_citations(msg["content"]))
                else:
                    st.markdown(msg["content"])
                if msg.get("citations"):
                    with st.expander("📄 Retrieved Source Documents"):
                        for c in msg["citations"]:
                            st.markdown(f"- **`{c['doc_id']}`** (Hybrid relevance: `{c.get('hybrid_score', 0):.3f}`)")

        user_input = st.chat_input("Ask about bank systems, incidents, payment gateways, runbooks...")


    with activity_col:
        st.subheader("🔎 Agent Activity Panel")
        activity_placeholder = st.empty()

        def render_activity(state: dict):
            with activity_placeholder.container():
                st.markdown(f"**Current node:** `{state.get('next_agent', '-')}`")
                st.markdown(f"**Chunks retrieved:** `{state.get('retrieved_count', 0)}`")

                warnings = state.get("guardrail_warnings", [])
                if warnings:
                    st.markdown("**Validation results:** ⚠️ Guardrails triggered")
                    for w in warnings:
                        st.warning(w)
                else:
                    st.markdown("**Validation results:** ✅ Passed")

                st.markdown("**Tool calls:**")
                for t in state.get("tool_calls", []):
                    icon = {"success": "✅", "error": "❌", "blocked": "🚫"}.get(t.get("status"), "•")
                    st.markdown(f"- {icon} `{t['tool']}`: {t.get('result_summary', '')}")

                st.markdown("**Node execution log:**")
                for e in state.get("activity_log", []):
                    st.markdown(f"- `[{e['node']}]` {e['event']}: {e.get('detail', '')}")

    # Process user question
    if user_input:
        current_messages.append({"role": "user", "content": user_input})
        with chat_col:
            with st.chat_message("user"):
                st.markdown(user_input)

        payload = {
            "session_id": st.session_state.session_id,
            "message": user_input,
            "deep_research": deep_research,
        }

        final_answer = ""
        citations = []
        last_state = {}

        try:
            with requests.post(
                f"{BACKEND_URL}/chat/stream",
                json=payload,
                headers=auth_headers,
                stream=True,
                timeout=120,
            ) as resp:
                if resp.status_code == 401:
                    st.error("Session expired — please sign in again.")
                    st.session_state.token = None
                    st.rerun()
                elif resp.status_code == 403:
                    st.error("Action forbidden by RBAC policy.")
                    st.stop()

                for line in resp.iter_lines(decode_unicode=True):
                    if not line or not line.startswith("data: "):
                        continue
                    data = json.loads(line[len("data: "):])
                    if data["type"] == "state_update":
                        last_state = data
                        render_activity(last_state)
                    elif data["type"] == "final":
                        final_answer = data["answer"]
                        citations = data.get("citations", [])
                    elif data["type"] == "error":
                        st.error(data["detail"])
        except requests.RequestException as exc:
            st.error(f"Connection to backend failed: {exc}")

        if final_answer:
            current_messages.append({"role": "assistant", "content": final_answer, "citations": citations})
            with chat_col:
                with st.chat_message("assistant"):
                    st.markdown(format_citations(final_answer))
                    if citations:

                        with st.expander("📄 Retrieved Source Documents"):
                            for c in citations:
                                st.markdown(f"- **`{c['doc_id']}`** (Hybrid score: `{c.get('hybrid_score', 0):.3f}`)")

# ==============================================================================
# TAB 2: 🔎 Search Documents & 📄 View Retrieved Documents
# ==============================================================================
with tabs[1]:
    st.subheader("🔎 Knowledge Base Search & Document Viewer")
    st.caption("Direct hybrid search (dense embeddings + BM25 sparse) respecting your role's access boundary.")

    col_q, col_dept, col_type = st.columns([3, 1, 1])
    with col_q:
        search_query = st.text_input("Search query", placeholder="e.g. payment gateway timeout or TLS certificate")
    with col_dept:
        search_dept = st.selectbox("Department", ["All", "payments", "platform", "risk", "general"])
    with col_type:
        search_type = st.selectbox("Document Type", ["All", "incident", "architecture", "runbook", "policy", "guideline"])

    if st.button("Search Knowledge Base", type="primary"):
        if search_query.strip():
            with st.spinner("Searching..."):
                try:
                    payload = {
                        "query": search_query,
                        "department": None if search_dept == "All" else search_dept,
                        "document_type": None if search_type == "All" else search_type,
                        "top_k": 8,
                    }
                    resp = requests.post(f"{BACKEND_URL}/tools/search", json=payload, headers=auth_headers, timeout=15)
                    if resp.status_code == 200:
                        results = resp.json().get("results", [])
                        st.success(f"Found {len(results)} matching document chunks.")

                        for i, r in enumerate(results):
                            meta = r.get("metadata", {})
                            with st.expander(
                                f"📄 [{i+1}] {meta.get('title', r['doc_id'])} — Dept: `{meta.get('department')}` | Type: `{meta.get('document_type')}` | Access: `{meta.get('access_level')}` (Score: {r['hybrid_score']:.3f})"
                            ):
                                st.markdown(f"**Chunk ID:** `{r['chunk_id']}`")
                                st.markdown(
                                    f"**Dense Score:** `{r['dense_score']}` | **Sparse Score:** `{r['sparse_score']}` | **Hybrid Score:** `{r['hybrid_score']}`"
                                )
                                st.markdown(f"**Date:** `{meta.get('created_date')}`")
                                st.markdown("---")
                                st.markdown(r["text"])
                    else:
                        st.error(f"Search failed: {resp.text}")
                except Exception as ex:
                    st.error(f"Request error: {ex}")
        else:
            st.warning("Please enter a search query.")

# ==============================================================================
# TAB 3: 📊 Python Data Analysis (Analyst & Administrator)
# ==============================================================================
if role in ["analyst", "administrator"]:
    with tabs[2]:
        st.subheader("📊 Python Data Analysis Tool")
        st.caption("Perform structured, safe data analytics over knowledge base incidents and records.")

        col_op, col_fdept, col_ftype = st.columns(3)
        with col_op:
            operation = st.selectbox(
                "Analysis Operation",
                ["count_by_field", "count_by_month", "top_keywords"],
            )
        with col_fdept:
            filter_dept = st.selectbox("Department Filter", ["All", "payments", "platform", "risk"], key="ana_dept")
        with col_ftype:
            filter_type = st.selectbox("Document Type Filter", ["All", "incident", "architecture", "policy"], key="ana_type")

        params = {}
        if operation == "count_by_field":
            target_field = st.selectbox("Target Field to Count", ["document_type", "department", "access_level"])
            params["field"] = target_field
        elif operation == "top_keywords":
            num_words = st.slider("Number of top keywords", min_value=5, max_value=25, value=10)
            params["n"] = num_words

        if st.button("Run Python Analysis", type="primary"):
            with st.spinner("Executing analysis..."):
                try:
                    payload = {
                        "operation": operation,
                        "params": params,
                        "department": None if filter_dept == "All" else filter_dept,
                        "document_type": None if filter_type == "All" else filter_type,
                    }
                    resp = requests.post(
                        f"{BACKEND_URL}/tools/python-analysis",
                        json=payload,
                        headers=auth_headers,
                        timeout=15,
                    )
                    if resp.status_code == 200:
                        res = resp.json()
                        st.success(f"Analysis completed across {res['records_analyzed']} records.")
                        analysis_data = res.get("analysis", {})

                        if "counts" in analysis_data:
                            counts = analysis_data["counts"]
                            st.write("### Frequency Distribution")
                            st.bar_chart(counts)
                            st.dataframe(
                                [{"Category": k, "Count": v} for k, v in counts.items()],
                                use_container_width=True,
                            )
                        elif "top_keywords" in analysis_data:
                            keywords = analysis_data["top_keywords"]
                            st.write("### Top Keywords")
                            kw_dict = {kw: count for kw, count in keywords}
                            st.bar_chart(kw_dict)
                            st.dataframe(
                                [{"Keyword": kw, "Frequency": count} for kw, count in keywords],
                                use_container_width=True,
                            )
                        else:
                            st.json(analysis_data)
                    else:
                        st.error(f"Analysis error: {resp.text}")
                except Exception as ex:
                    st.error(f"Error executing analysis: {ex}")

# ==============================================================================
# TAB 4: 🔧 MCP Tools (Analyst & Administrator)
# ==============================================================================
if role in ["analyst", "administrator"]:
    with tabs[3]:
        st.subheader("🔧 Model Context Protocol (MCP) Tools")
        st.caption("Live external integration querying mock enterprise directory services.")

        col_m1, col_m2 = st.columns([1, 3])
        with col_m1:
            mcp_resource = st.selectbox("Enterprise Resource", ["employees", "services", "incidents"])
        with col_m2:
            mcp_query = st.text_input("Filter query (optional)", placeholder="e.g. payment, Priya, SVC-PAY-01, SEV1")

        if st.button("Query MCP Service", type="primary"):
            with st.spinner("Invoking MCP..."):
                try:
                    resp = requests.get(
                        f"{BACKEND_URL}/tools/mcp/{mcp_resource}",
                        params={"q": mcp_query},
                        headers=auth_headers,
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        results = data.get("results", [])
                        st.success(f"Retrieved {len(results)} items from `{mcp_resource}`.")
                        st.dataframe(results, use_container_width=True)
                        with st.expander("Inspect Raw JSON Response"):
                            st.json(data)
                    else:
                        st.error(f"MCP lookup failed: {resp.text}")
                except Exception as ex:
                    st.error(f"MCP connection error: {ex}")

# ==============================================================================
# TAB 5: 📈 Analytics (Analyst & Administrator)
# ==============================================================================
if role in ["analyst", "administrator"]:
    with tabs[4]:
        st.subheader("📈 Assistant Usage & Operational Analytics")
        st.caption("Telemetry, rate-limiting status, and event distribution.")

        try:
            resp = requests.get(f"{BACKEND_URL}/tools/analytics", headers=auth_headers, timeout=10)
            if resp.status_code == 200:
                stats = resp.json()

                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                col_m1.metric("Indexed Chunks", stats.get("total_indexed_chunks", 0))
                col_m2.metric("Active Sessions", stats.get("active_sessions_count", 0))
                col_m3.metric("Audit Events Captured", stats.get("total_audit_events", 0))
                rl = stats.get("rate_limit_status", {})
                col_m4.metric("Rate Limit Tokens", f"{rl.get('current_tokens', 0)} / {rl.get('capacity', 0)}")

                st.divider()

                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    st.markdown("#### Event Type Breakdown")
                    events = stats.get("event_distribution", {})
                    if events:
                        st.bar_chart(events)
                    else:
                        st.info("No events recorded yet.")
                with col_c2:
                    st.markdown("#### User Activity Distribution")
                    users = stats.get("user_activity", {})
                    if users:
                        st.dataframe(
                            [{"User": u, "Activity Count": c} for u, c in users.items()],
                            use_container_width=True,
                        )
                    else:
                        st.info("No user activity logs yet.")
            else:
                st.error("Failed to load analytics.")
        except Exception as ex:
            st.error(f"Could not load analytics: {ex}")

# ==============================================================================
# TAB 6: 🛠️ Admin Console (Administrator Only)
# ==============================================================================
if role == "administrator":
    with tabs[5]:
        st.subheader("🛠️ Administrator Console")
        st.caption("Full enterprise management: users, roles, knowledge base, configurations, and audit logs.")

        admin_tabs = st.tabs(
            [
                "👥 Manage Users",
                "🔐 Roles & Permissions",
                "📚 Knowledge Base",
                "➕ Upload Document",
                "🗑️ Delete Document",
                "⚙️ System Config",
                "📋 Audit Logs",
            ]
        )

        # 1. 👥 Manage Users
        with admin_tabs[0]:
            st.markdown("### 👥 System User Management")
            try:
                uresp = requests.get(f"{BACKEND_URL}/admin/users", headers=auth_headers, timeout=10)
                if uresp.status_code == 200:
                    users_data = uresp.json().get("users", [])
                    st.dataframe(users_data, use_container_width=True)
            except Exception as e:
                st.error(f"Failed to fetch users: {e}")

            st.markdown("#### ➕ Add or Update User")
            with st.form("create_user_form"):
                new_uname = st.text_input("Username")
                new_pwd = st.text_input("Password", type="password")
                new_role = st.selectbox("Role", ["viewer", "analyst", "administrator"])
                new_dept = st.selectbox("Department", ["general", "payments", "platform", "risk"])
                create_submit = st.form_submit_button("Save User")
                if create_submit:
                    if new_uname and new_pwd:
                        try:
                            cresp = requests.post(
                                f"{BACKEND_URL}/admin/users",
                                json={
                                    "username": new_uname,
                                    "password": new_pwd,
                                    "role": new_role,
                                    "department": new_dept,
                                },
                                headers=auth_headers,
                                timeout=10,
                            )
                            if cresp.status_code == 200:
                                st.success(f"User `{new_uname}` saved successfully.")
                                st.rerun()
                            else:
                                st.error(f"Failed: {cresp.text}")
                        except Exception as e:
                            st.error(f"Error saving user: {e}")
                    else:
                        st.warning("Please provide username and password.")

        # 2. 🔐 Roles & Permissions
        with admin_tabs[1]:
            st.markdown("### 🔐 Role-Based Access Matrix")
            try:
                rresp = requests.get(f"{BACKEND_URL}/admin/roles", headers=auth_headers, timeout=10)
                if rresp.status_code == 200:
                    rdata = rresp.json()
                    matrix = rdata.get("matrix", {})
                    all_perms = rdata.get("all_permissions", [])

                    # Construct display table
                    matrix_rows = []
                    for perm in all_perms:
                        matrix_rows.append(
                            {
                                "Permission": perm,
                                "Viewer": "✅" if perm in matrix.get("viewer", []) else "❌",
                                "Analyst": "✅" if perm in matrix.get("analyst", []) else "❌",
                                "Administrator": "✅" if perm in matrix.get("administrator", []) else "❌",
                            }
                        )
                    st.dataframe(matrix_rows, use_container_width=True)
            except Exception as e:
                st.error(f"Error fetching roles: {e}")

        # 3. 📚 Knowledge Base Management & Reindex
        with admin_tabs[2]:
            st.markdown("### 📚 Knowledge Base Indexing")
            try:
                dresp = requests.get(f"{BACKEND_URL}/admin/documents", headers=auth_headers, timeout=10)
                if dresp.status_code == 200:
                    kb_info = dresp.json()
                    st.metric("Total Documents Indexed", kb_info.get("total_documents", 0))
                    st.metric("Total Searchable Chunks", kb_info.get("total_chunks", 0))

                    if st.button("🔄 Trigger Full Knowledge Base Reindex (`admin_reindex`)", type="primary"):
                        with st.spinner("Reindexing chunks and vector store..."):
                            re_resp = requests.post(f"{BACKEND_URL}/admin/reindex", headers=auth_headers, timeout=30)
                            if re_resp.status_code == 200:
                                st.success(f"Reindexed successfully! Total chunks: {re_resp.json().get('total_chunks')}")
                                st.rerun()
                            else:
                                st.error(f"Reindex failed: {re_resp.text}")
            except Exception as e:
                st.error(f"Error loading knowledge base info: {e}")

        # 4. ➕ Upload Document
        with admin_tabs[3]:
            st.markdown("### ➕ Upload / Ingest New Knowledge Document")
            with st.form("doc_upload_form"):
                doc_title = st.text_input("Document Title", placeholder="e.g. Core Banking High Availability Architecture")
                col_u1, col_u2, col_u3 = st.columns(3)
                with col_u1:
                    doc_dept = st.selectbox("Department", ["general", "payments", "platform", "risk"], key="up_dept")
                with col_u2:
                    doc_type = st.selectbox("Document Type", ["incident", "architecture", "runbook", "policy", "guideline"], key="up_type")
                with col_u3:
                    doc_access = st.selectbox("Access Level", ["internal", "restricted", "confidential"], key="up_access")

                doc_date = st.text_input("Created Date (YYYY-MM-DD)", value="2025-09-01")
                doc_content = st.text_area("Document Markdown Content", height=250, placeholder="# Title\n\nDetails...")
                upload_submit = st.form_submit_button("Ingest Document")

                if upload_submit:
                    if doc_title and doc_content:
                        with st.spinner("Ingesting and indexing document..."):
                            try:
                                up_payload = {
                                    "title": doc_title,
                                    "content": doc_content,
                                    "department": doc_dept,
                                    "document_type": doc_type,
                                    "access_level": doc_access,
                                    "created_date": doc_date,
                                }
                                up_resp = requests.post(
                                    f"{BACKEND_URL}/admin/documents/upload",
                                    json=up_payload,
                                    headers=auth_headers,
                                    timeout=20,
                                )
                                if up_resp.status_code == 200:
                                    st.success(f"Document `{up_resp.json().get('doc_id')}` uploaded and indexed!")
                                    st.rerun()
                                else:
                                    st.error(f"Upload failed: {up_resp.text}")
                            except Exception as e:
                                st.error(f"Upload error: {e}")
                    else:
                        st.warning("Please provide both title and content.")

        # 5. 🗑️ Delete Document
        with admin_tabs[4]:
            st.markdown("### 🗑️ Delete Document from Knowledge Base")
            try:
                del_resp = requests.get(f"{BACKEND_URL}/admin/documents", headers=auth_headers, timeout=10)
                if del_resp.status_code == 200:
                    docs = del_resp.json().get("documents", [])
                    if docs:
                        for d in docs:
                            col_d1, col_d2 = st.columns([4, 1])
                            with col_d1:
                                st.markdown(
                                    f"📄 **{d.get('title', d['doc_id'])}** (`{d['filename']}`)\n"
                                    f"- Dept: `{d['department']}` | Type: `{d['document_type']}` | Access: `{d['access_level']}` | Size: `{d['size_bytes']} bytes`"
                                )
                            with col_d2:
                                if st.button("Delete 🗑️", key=f"del_{d['doc_id']}"):
                                    res = requests.delete(
                                        f"{BACKEND_URL}/admin/documents/{d['doc_id']}",
                                        headers=auth_headers,
                                        timeout=10,
                                    )
                                    if res.status_code == 200:
                                        st.success(f"Deleted `{d['doc_id']}`")
                                        st.rerun()
                                    else:
                                        st.error(f"Delete failed: {res.text}")
                            st.divider()
                    else:
                        st.info("No documents in repository.")
            except Exception as e:
                st.error(f"Error fetching documents list: {e}")

        # 6. ⚙️ System Configuration
        with admin_tabs[5]:
            st.markdown("### ⚙️ Runtime System Configuration")
            try:
                cfg_resp = requests.get(f"{BACKEND_URL}/admin/config", headers=auth_headers, timeout=10)
                if cfg_resp.status_code == 200:
                    cfg = cfg_resp.json()
                    st.json(cfg)

                    st.markdown("#### Tweak Operational Parameters")
                    with st.form("config_form"):
                        new_temp = st.slider("LLM Temperature", 0.0, 1.0, float(cfg.get("temperature", 0.2)), step=0.05)
                        new_cap = st.number_input("Rate Limit Bucket Capacity", min_value=1, value=int(cfg.get("rate_limit_capacity", 20)))
                        new_refill = st.number_input("Rate Limit Refill Rate (tokens/sec)", min_value=0.1, value=float(cfg.get("rate_limit_refill_rate", 2.0)))
                        update_cfg = st.form_submit_button("Update Configuration")

                        if update_cfg:
                            try:
                                upd = requests.post(
                                    f"{BACKEND_URL}/admin/config",
                                    json={
                                        "llm_temperature": new_temp,
                                        "rate_limit_capacity": new_cap,
                                        "rate_limit_refill_rate": new_refill,
                                    },
                                    headers=auth_headers,
                                    timeout=10,
                                )
                                if upd.status_code == 200:
                                    st.success("System configuration updated!")
                                    st.rerun()
                                else:
                                    st.error(f"Failed to update config: {upd.text}")
                            except Exception as e:
                                st.error(f"Error updating config: {e}")
            except Exception as e:
                st.error(f"Error loading system config: {e}")

        # 7. 📋 View System / Audit Logs
        with admin_tabs[6]:
            st.markdown("### 📋 Security & Audit Logs")
            try:
                lresp = requests.get(f"{BACKEND_URL}/admin/logs?limit=150", headers=auth_headers, timeout=10)
                if lresp.status_code == 200:
                    logs_data = lresp.json().get("logs", [])
                    st.caption(f"Showing last {len(logs_data)} audit entries (immutable ring buffer).")

                    filter_kw = st.text_input("Filter logs by keyword / event", placeholder="e.g. guardrail, rbac, tool_call, reindex")
                    if filter_kw:
                        logs_data = [l for l in logs_data if filter_kw.lower() in json.dumps(l).lower()]

                    if logs_data:
                        st.dataframe(logs_data, use_container_width=True)
                    else:
                        st.info("No matching logs.")
            except Exception as e:
                st.error(f"Error loading logs: {e}")
