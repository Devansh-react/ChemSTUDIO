"""Streamlit test interface for the Chem Process Studio FastAPI workflow."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import requests
import streamlit as st


API_BASE_URL = os.getenv(
    "CHEMSTUDIO_API_URL",
    "http://127.0.0.1:8000",
).rstrip("/")
UPLOAD_DIRECTORY = Path(
    os.getenv(
        "CHEMSTUDIO_UPLOAD_DIRECTORY",
        "database/uploads",
    )
)


def save_uploaded_pdfs(uploaded_files: list[Any]) -> list[str]:
    """Save uploads once by content hash and return server-local paths."""
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


def predict(payload: dict[str, Any]) -> dict[str, Any]:
    """Call the locally running Chem Process Studio FastAPI endpoint."""
    response = requests.post(
        f"{API_BASE_URL}/predict",
        json=payload,
        timeout=180,
    )
    response.raise_for_status()
    return response.json()


def render_retrieved_context(metadata: dict[str, Any]) -> None:
    """Show ingestion information returned by the FastAPI response."""
    ingestion_results = metadata.get("ingestion_results", [])

    if not ingestion_results:
        return

    st.subheader("Document ingestion")

    for result in ingestion_results:
        status = "Indexed" if result.get("success") else "Failed"
        title = Path(result.get("path", "document")).name

        with st.expander(f"{status}: {title}", expanded=False):
            if result.get("success"):
                st.json(
                    {
                        "document_id": result.get("document_id"),
                        "total_pages": result.get("total_pages"),
                        "chunks_created": result.get("chunks_created"),
                        "chroma": result.get("chroma"),
                        "bm25": result.get("bm25"),
                    }
                )
            else:
                st.error(result.get("error", "Unknown ingestion error"))


def main() -> None:
    st.set_page_config(
        page_title="Chem Process Studio",
        page_icon="⚗️",
        layout="wide",
    )

    st.title("Chem Process Studio")
    st.caption("Test the local FastAPI workflow and optional literature RAG pipeline.")

    with st.sidebar:
        st.header("Connection")
        st.code(API_BASE_URL)
        st.caption("Start FastAPI before submitting a prediction.")

    with st.form("prediction_form"):
        reactants = st.text_area(
            "Reactant SMILES",
            placeholder="Example: CCO.CCBr",
            help="Use dot-separated reactant SMILES.",
        )

        mechanism = st.selectbox(
            "Reaction mechanism",
            options=["SN1", "SN2", "E1", "E2", "Oxidation", "Reduction"],
        )

        st.subheader("Conditions")
        condition_left, condition_right = st.columns(2)

        with condition_left:
            solvent = st.text_input("Solvent", placeholder="DMF")
            catalyst = st.text_input("Catalyst", placeholder="Optional")
            temperature = st.text_input("Temperature", placeholder="e.g. 80 C")

        with condition_right:
            pressure = st.text_input("Pressure", placeholder="Optional")
            reaction_time = st.text_input("Reaction time", placeholder="e.g. 2 h")
            reagents = st.text_input("Reagents", placeholder="Optional")

        uploaded_pdfs = st.file_uploader(
            "Supporting literature PDFs (optional)",
            type=["pdf"],
            accept_multiple_files=True,
            help="Uploaded PDFs are indexed into Chroma and BM25 before prediction.",
        )

        submitted = st.form_submit_button("Run prediction", type="primary")

    if not submitted:
        return

    if not reactants.strip():
        st.error("Reactant SMILES are required.")
        return

    conditions = {
        key: value
        for key, value in {
            "solvent": solvent,
            "catalyst": catalyst,
            "temperature": temperature,
            "pressure": pressure,
            "time": reaction_time,
            "reagents": reagents,
        }.items()
        if value.strip()
    }

    try:
        pdf_context = save_uploaded_pdfs(uploaded_pdfs)

        with st.spinner("Running validation, retrieval, prediction, and verification..."):
            result = predict(
                {
                    "reactants": reactants.strip(),
                    "mechanism": mechanism,
                    "conditions": conditions,
                    "pdf_context": pdf_context,
                    "metadata": {"source": "streamlit_test_ui"},
                }
            )

    except requests.RequestException as error:
        st.error(
            f"Could not reach the FastAPI service at {API_BASE_URL}. {error}"
        )
        return
    except OSError as error:
        st.error(f"Could not save uploaded PDF(s). {error}")
        return

    if result.get("success"):
        st.success("Workflow completed.")
    else:
        st.error("Workflow did not complete successfully.")

    summary_left, summary_right = st.columns(2)

    with summary_left:
        st.subheader("Prediction")
        st.code(result.get("prediction") or "Not available")
        st.write("**Mechanism:**", result.get("mechanism") or "Not available")

    with summary_right:
        st.subheader("Verification")
        st.json(result.get("verification") or {})

    if result.get("explanation"):
        st.subheader("Explanation")
        st.markdown(result["explanation"])

    warnings = result.get("warnings", [])
    if warnings:
        st.subheader("Warnings")
        for warning in warnings:
            st.warning(warning)

    metadata = result.get("metadata") or {}
    render_retrieved_context(metadata)

    with st.expander("Raw API response"):
        st.json(result)


if __name__ == "__main__":
    main()
