"""Streamlit test interface for Chem Process Studio with Auth UI."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import requests
import streamlit as st


# ──────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────
API_BASE_URL = os.getenv("CHEMSTUDIO_API_URL", "http://127.0.0.1:8000").rstrip("/")
UPLOAD_DIRECTORY = Path(os.getenv("CHEMSTUDIO_UPLOAD_DIRECTORY", "database/uploads"))

# ──────────────────────────────────────────────────────────────
# Session State Initialization
# ──────────────────────────────────────────────────────────────
def init_session_state():
    defaults = {
        "api_key": None,
        "user_info": None,
        "page": "predict",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ──────────────────────────────────────────────────────────────
# API Helpers
# ──────────────────────────────────────────────────────────────
def api_request(method: str, endpoint: str, **kwargs) -> requests.Response:
    headers = kwargs.pop("headers", {})
    if st.session_state.api_key:
        headers["X-API-Key"] = st.session_state.api_key
    url = f"{API_BASE_URL}{endpoint}"
    return requests.request(method, url, headers=headers, timeout=180, **kwargs)


def auth_register(email: str, password: str, full_name: str = "", organization: str = "") -> dict:
    resp = api_request("POST", "/auth/register", json={
        "email": email,
        "password": password,
        "full_name": full_name,
        "organization": organization,
    })
    resp.raise_for_status()
    return resp.json()


def auth_login(email: str, password: str) -> dict:
    resp = api_request("POST", "/auth/login", json={
        "email": email,
        "password": password,
    })
    resp.raise_for_status()
    return resp.json()


def auth_logout() -> dict:
    resp = api_request("POST", "/auth/logout")
    resp.raise_for_status()
    return resp.json()


def get_user_profile() -> dict:
    resp = api_request("GET", "/auth/me")
    resp.raise_for_status()
    return resp.json()


def create_api_key(name: str, scopes: list[str], expires_in_days: int | None = None) -> dict:
    payload = {"name": name, "scopes": scopes}
    if expires_in_days:
        payload["expires_in_days"] = expires_in_days
    resp = api_request("POST", "/auth/api-keys", json=payload)
    resp.raise_for_status()
    return resp.json()


def list_api_keys() -> list[dict]:
    resp = api_request("GET", "/auth/api-keys")
    resp.raise_for_status()
    return resp.json()


def revoke_api_key(key_prefix: str) -> dict:
    resp = api_request("DELETE", f"/auth/api-keys/{key_prefix}")
    resp.raise_for_status()
    return resp.json()


def predict(payload: dict[str, Any]) -> dict[str, Any]:
    resp = api_request("POST", "/predict", json=payload)
    resp.raise_for_status()
    return resp.json()


def save_uploaded_pdfs(uploaded_files: list[Any]) -> list[str]:
    if not uploaded_files:
        return []
    UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    saved_paths: list[str] = []
    for uploaded_file in uploaded_files:
        content = uploaded_file.getvalue()
        content_hash = hashlib.sha256(content).hexdigest()[:16]
        safe_name = Path(uploaded_file.name).name
        destination = UPLOAD_DIRECTORY / f"{content_hash}_{safe_name}"
        if not destination.exists():
            destination.write_bytes(content)
        saved_paths.append(str(destination.resolve()))
    return saved_paths


# ──────────────────────────────────────────────────────────────
# UI Components
# ──────────────────────────────────────────────────────────────
def render_header():
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("⚗️ Chem Process Studio")
        st.caption("AI-assisted reaction prediction with literature-grounded retrieval")
    with col2:
        if st.session_state.user_info:
            user = st.session_state.user_info
            st.markdown(f"""
            <div style="text-align:right; padding: 10px; background:#f0f2f6; border-radius:8px;">
                <strong>👤 {user.get('full_name') or user['email']}</strong><br>
                <small>{user['email']}</small>
            </div>
            """, unsafe_allow_html=True)
            if st.button("🚪 Logout", use_container_width=True):
                try:
                    auth_logout()
                except Exception:
                    pass
                st.session_state.api_key = None
                st.session_state.user_info = None
                st.rerun()
        else:
            if st.button("🔐 Login / Register", use_container_width=True):
                st.session_state.page = "auth"
                st.rerun()


def render_auth_page():
    st.header("🔐 Authentication")
    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="user@lab.com")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", type="primary", use_container_width=True)
            if submitted:
                if not email or not password:
                    st.error("Email and password required")
                else:
                    try:
                        with st.spinner("Logging in..."):
                            data = auth_login(email, password)
                        st.session_state.api_key = data["api_key"]["api_key"]
                        st.session_state.user_info = data["user"]
                        st.success("Logged in successfully!")
                        st.session_state.page = "predict"
                        st.rerun()
                    except requests.HTTPError as e:
                        try:
                            detail = e.response.json().get('detail', str(e))
                        except Exception:
                            detail = f"Server returned: {e.response.status_code} - {e.response.text[:200]}"
                        st.error(f"Login failed: {detail}")
                    except requests.ConnectionError:
                        st.error("Cannot connect to API server. Is it running at http://127.0.0.1:8000?")
                    except Exception as e:
                        st.error(f"Connection error: {e}")

    with tab_register:
        with st.form("register_form"):
            email = st.text_input("Email", placeholder="user@lab.com")
            full_name = st.text_input("Full Name (optional)", placeholder="Dr. Jane Smith")
            organization = st.text_input("Organization (optional)", placeholder="Acme Pharma")
            password = st.text_input("Password", type="password", help="Minimum 8 characters")
            password2 = st.text_input("Confirm Password", type="password")
            submitted = st.form_submit_button("Create Account", type="primary", use_container_width=True)
            if submitted:
                if not email or not password:
                    st.error("Email and password required")
                elif password != password2:
                    st.error("Passwords do not match")
                elif len(password) < 8:
                    st.error("Password must be at least 8 characters")
                else:
                    try:
                        with st.spinner("Creating account..."):
                            data = auth_register(email, password, full_name, organization)
                        st.session_state.api_key = data["api_key"]["api_key"]
                        st.session_state.user_info = data["user"]
                        st.success("Account created! Your API key is shown below — save it now!")
                        st.code(data["api_key"]["api_key"], language=None)
                        st.warning("⚠️ This API key will not be shown again. Copy it now.")
                        st.session_state.page = "predict"
                        st.rerun()
                    except requests.HTTPError as e:
                        try:
                            detail = e.response.json().get('detail', str(e))
                        except Exception:
                            detail = f"Server returned: {e.response.status_code} - {e.response.text[:200]}"
                        st.error(f"Registration failed: {detail}")
                    except requests.ConnectionError:
                        st.error("Cannot connect to API server. Is it running at http://127.0.0.1:8000?")
                    except Exception as e:
                        st.error(f"Connection error: {e}")


def render_api_keys_page():
    st.header("🔑 API Key Management")
    st.caption("Create and manage API keys for programmatic access")

    # Create new key
    with st.expander("➕ Create New API Key", expanded=False):
        with st.form("create_key_form"):
            name = st.text_input("Key Name", placeholder="e.g., CI/CD Pipeline, Lab Notebook")
            scopes = st.multiselect(
                "Scopes (Permissions)",
                options=["predict", "validate", "explain", "documents:read", "documents:write", "reviews:read", "reviews:write"],
                default=["predict"],
                help="Select what this key can access"
            )
            expires_days = st.number_input("Expires in (days, optional)", min_value=1, max_value=365, value=30, step=1)
            no_expiry = st.checkbox("No expiry", value=False)
            submitted = st.form_submit_button("Generate Key", type="primary")
            if submitted:
                if not name.strip():
                    st.error("Key name required")
                elif not scopes:
                    st.error("Select at least one scope")
                else:
                    try:
                        with st.spinner("Generating..."):
                            data = create_api_key(name, scopes, None if no_expiry else expires_days)
                        st.success("API key created! Save it now — it won't be shown again.")
                        st.code(data["api_key"], language=None)
                        st.warning("⚠️ Copy this key immediately. It cannot be retrieved later.")
                    except requests.HTTPError as e:
                        try:
                            detail = e.response.json().get('detail', str(e))
                        except Exception:
                            detail = f"Server returned: {e.response.status_code} - {e.response.text[:200]}"
                        st.error(f"Failed: {detail}")
                    except requests.ConnectionError:
                        st.error("Cannot connect to API server. Is it running at http://127.0.0.1:8000?")
                    except Exception as e:
                        st.error(f"Failed: {e}")

    # List existing keys
    st.subheader("Your API Keys")
    try:
        keys = list_api_keys()
        if not keys:
            st.info("No API keys yet. Create one above.")
        else:
            for key in keys:
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 2, 1])
                    with col1:
                        st.markdown(f"**{key['name']}**  \n`{key['key_prefix']}...`")
                        scopes_badge = " ".join([f"`{s}`" for s in key['scopes']])
                        st.caption(f"Scopes: {scopes_badge}")
                    with col2:
                        if key['expires_at']:
                            st.caption(f"Expires: {key['expires_at'][:10]}")
                        else:
                            st.caption("No expiry")
                        st.caption(f"Created: {key['created_at'][:10]}")
                    with col3:
                        if st.button("🗑️ Revoke", key=f"revoke_{key['key_prefix']}", use_container_width=True):
                            try:
                                revoke_api_key(key['key_prefix'])
                                st.success("Revoked")
                                st.rerun()
                            except requests.HTTPError as e:
                                try:
                                    detail = e.response.json().get('detail', str(e))
                                except Exception:
                                    detail = f"Server returned: {e.response.status_code} - {e.response.text[:200]}"
                                st.error(f"Failed: {detail}")
                            except requests.ConnectionError:
                                st.error("Cannot connect to API server. Is it running at http://127.0.0.1:8000?")
                            except Exception as e:
                                st.error(f"Failed: {e}")
    except requests.ConnectionError:
        st.error("Cannot connect to API server. Is it running at http://127.0.0.1:8000?")
    except Exception as e:
        st.error(f"Could not load keys: {e}")


def render_profile_page():
    st.header("👤 Profile")
    user = st.session_state.user_info
    if not user:
        st.warning("Not logged in")
        return

    col1, col2 = st.columns([1, 2])
    with col1:
        st.image(f"https://ui-avatars.com/api/?name={user.get('full_name') or user['email']}&background=0D8ABC&color=fff", width=120)
    with col2:
        st.markdown(f"### {user.get('full_name') or 'User'}")
        st.markdown(f"**Email:** {user['email']}")
        st.markdown(f"**Organization:** {user.get('organization') or '—'}")
        st.markdown(f"**Role:** {user['role']}")
        st.markdown(f"**Member since:** {user['created_at'][:10]}")


def render_predict_page():
    st.header("🔮 Reaction Prediction")

    with st.form("prediction_form"):
        reactants = st.text_area(
            "Reactant SMILES",
            placeholder="Example: CCO.CCBr",
            help="Dot-separated reactant SMILES",
        )

        mechanism = st.selectbox(
            "Mechanism",
            options=["SN1", "SN2", "E1", "E2", "Oxidation", "Reduction", "Esterification", "Other"],
        )

        st.subheader("Conditions")
        cl, cr = st.columns(2)
        with cl:
            solvent = st.text_input("Solvent", placeholder="DMF")
            catalyst = st.text_input("Catalyst", placeholder="Optional")
            temperature = st.text_input("Temperature", placeholder="e.g., 80 C")
        with cr:
            pressure = st.text_input("Pressure", placeholder="Optional")
            reaction_time = st.text_input("Time", placeholder="e.g., 2 h")
            reagents = st.text_input("Reagents", placeholder="Optional")

        uploaded_pdfs = st.file_uploader(
            "Supporting PDFs (optional)",
            type=["pdf"],
            accept_multiple_files=True,
        )

        submitted = st.form_submit_button("🚀 Run Prediction", type="primary", use_container_width=True)

    if not submitted:
        return
    if not reactants.strip():
        st.error("Reactant SMILES required")
        return

    conditions = {k: v for k, v in {
        "solvent": solvent, "catalyst": catalyst, "temperature": temperature,
        "pressure": pressure, "time": reaction_time, "reagents": reagents,
    }.items() if v.strip()}

    try:
        pdf_context = save_uploaded_pdfs(uploaded_pdfs)
        with st.spinner("Running workflow..."):
            result = predict({
                "reactants": reactants.strip(),
                "mechanism": mechanism,
                "conditions": conditions,
                "pdf_context": pdf_context,
                "metadata": {"source": "streamlit_ui"},
            })
    except requests.HTTPError as e:
        try:
            detail = e.response.json().get('detail', str(e))
        except Exception:
            detail = f"Server returned: {e.response.status_code} - {e.response.text[:200]}"
        st.error(f"API error: {detail}")
        return
    except requests.ConnectionError:
        st.error("Cannot connect to API server. Is it running at http://127.0.0.1:8000?")
        return
    except Exception as e:
        st.error(f"Error: {e}")
        return

    # Results
    if result.get("success"):
        st.success("✅ Prediction completed")
    else:
        st.error("❌ Workflow failed")

    sl, sr = st.columns(2)
    with sl:
        st.subheader("Prediction")
        st.code(result.get("prediction") or "N/A")
        st.write("**Mechanism:**", result.get("mechanism") or "N/A")
    with sr:
        st.subheader("Verification")
        st.json(result.get("verification") or {})

    if result.get("explanation"):
        st.subheader("Explanation")
        st.markdown(result["explanation"])

    warnings = result.get("warnings", [])
    if warnings:
        st.subheader("Warnings")
        for w in warnings:
            st.warning(w)

    meta = result.get("metadata") or {}
    if meta.get("ingestion_results"):
        st.subheader("📄 Document Ingestion")
        for r in meta["ingestion_results"]:
            status = "✅" if r.get("success") else "❌"
            with st.expander(f"{status} {Path(r.get('path', '')).name}"):
                if r.get("success"):
                    st.json({k: r.get(k) for k in ["document_id", "total_pages", "chunks_created"]})
                else:
                    st.error(r.get("error", "Unknown"))

    if meta.get("retrieved_context"):
        st.subheader("📚 Retrieved Evidence")
        for item in meta["retrieved_context"]:
            with st.expander(f"{item.get('source', 'Unknown')}, p.{item.get('page', '?')}"):
                st.write(item.get("content", ""))
                st.caption(f"Score: {item.get('score', 0):.2f}")

    with st.expander("🔍 Raw Response"):
        st.json(result)


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="Chem Process Studio",
        page_icon="⚗️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Custom CSS
    st.markdown("""
    <style>
    .stApp { max-width: 1200px; margin: 0 auto; }
    .stButton>button { border-radius: 6px; }
    .stCodeBlock { background: #1e1e1e !important; }
    div[data-testid="stExpander"] { border: 1px solid #e0e0e0; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

    init_session_state()
    render_header()

    # Navigation
    if not st.session_state.api_key:
        render_auth_page()
        return

    # Authenticated pages
    pages = {
        "🔮 Predict": "predict",
        "🔑 API Keys": "api_keys",
        "👤 Profile": "profile",
    }
    page_labels = list(pages.keys())
    page_values = list(pages.values())

    # Sidebar navigation
    with st.sidebar:
        st.markdown("---")
        selected = st.radio("Navigate", page_labels, index=page_values.index(st.session_state.page))
        st.session_state.page = pages[selected]
        st.markdown("---")
        st.caption(f"API: {API_BASE_URL}")

    # Render selected page
    if st.session_state.page == "predict":
        render_predict_page()
    elif st.session_state.page == "api_keys":
        render_api_keys_page()
    elif st.session_state.page == "profile":
        render_profile_page()


if __name__ == "__main__":
    main()