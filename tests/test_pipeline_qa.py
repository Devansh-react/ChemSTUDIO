"""Deterministic QA contract tests for the reaction-prediction pipeline.

These tests deliberately replace the remote prediction service and vector index with
small fakes.  They test the product's orchestration policy, rather than treating an
unavailable external service as a product failure.  Run ``scripts/run_pipeline_qa.py``
to produce the human-readable report.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from agents.predictor import predict_reaction
from agents.validator import validate_agent
from graph.state import create_prediction_state
from middleware.post_review import require_post_prediction_review
from middleware.pre_review import build_pre_prediction_review
from middleware.retry import should_retry_prediction


PDF_FIXTURE = Path(__file__).parents[1] / "test_literature.pdf"


@pytest.mark.parametrize(
    ("name", "smiles", "valid", "canonical"),
    [
        ("ethanol", "CCO", True, "CCO"),
        ("ethyl_bromide", "CCBr", True, "CCBr"),
        ("acetic_acid", "CC(=O)O", True, "CC(=O)O"),
        ("benzene", "c1ccccc1", True, "c1ccccc1"),
        ("dot_separated_reactants", "CCBr.[Na+].[C-]#N", True, None),
        ("charged_reactant", "C[N+](C)(C)C", True, "C[N+](C)(C)C"),
        ("invalid_plain_text", "not a smiles", False, None),
        ("invalid_unclosed_ring", "C1CC", False, None),
        ("invalid_unclosed_branch", "CC(", False, None),
        ("invalid_element", "Xx", False, None),
        ("empty_input", "", False, None),
        ("radical_rejected", "[CH3]", False, None),
    ],
    ids=lambda value: str(value),
)
def test_smiles_validation_matrix(name: str, smiles: str, valid: bool, canonical: str | None):
    """Every input must be stopped or canonicalized before model invocation."""
    result = validate_agent(create_prediction_state(smiles, {}, "SN2"))
    assert result["validation"] is valid, name
    assert result["status"] == ("validated" if valid else "failed")
    if canonical is not None:
        assert result["canonical_smiles"] == canonical


@pytest.mark.parametrize(
    ("has_pdf", "conditions"),
    [
        (False, {}),
        (False, {"solvent": "DMF", "temperature": "25 C"}),
        (True, {"solvent": "DMF", "reagents": "NaCN"}),
    ],
    ids=["no_pdf_minimal", "no_pdf_conditions", "pdf_grounded"],
)
def test_preview_contains_exact_predictor_context(has_pdf: bool, conditions: dict[str, str]):
    """The preview must reveal the canonical reactants, conditions, and evidence."""
    state = create_prediction_state("CCBr.[Na+].[C-]#N", conditions, "SN2")
    state["canonical_smiles"] = "N#[C-].CCBr.[Na+]"
    state["retrieved_context"] = (
        [{"source": PDF_FIXTURE.name, "page": 1, "content": "DMF favors SN2."}]
        if has_pdf else []
    )
    preview = build_pre_prediction_review(state)
    assert preview["canonical_smiles"] == state["canonical_smiles"]
    assert preview["conditions"] == conditions
    assert preview["retrieved_context"] == state["retrieved_context"]


@pytest.mark.parametrize(
    ("name", "state_update", "retry", "target", "reason_part"),
    [
        ("low_confidence_first_attempt", {"confidence": 0.49}, True, "predictor", "Low confidence"),
        ("low_confidence_second_attempt", {"confidence": 0.10, "retry_count": {"predictor": 2, "retriever": 0, "verifier": 0, "workflow": 2}}, True, "predictor", "Low confidence"),
        ("low_confidence_exhausted", {"confidence": 0.10, "retry_count": {"predictor": 3, "retriever": 0, "verifier": 0, "workflow": 3}}, False, "none", "All validations"),
        ("invalid_product", {"validation_results": {"product_validation": False}}, True, "predictor", "Product validation failed"),
        ("invalid_context", {"validation_results": {"retrieved_context_validation": False}}, True, "retriever", "Retrieved context validation failed"),
        ("workflow_limit", {"retry_count": {"predictor": 0, "retriever": 0, "verifier": 0, "workflow": 5}}, False, "none", "Maximum workflow"),
    ],
    ids=lambda value: str(value),
)
def test_retry_policy_matrix(name, state_update, retry, target, reason_part):
    state = create_prediction_state("CCO", {}, "Oxidation")
    state["validation_results"] = {"product_validation": True, "mechanism_validation": True, "retrieved_context_validation": True}
    state.update(state_update)
    decision = should_retry_prediction(state)
    assert decision["retry"] is retry, name
    assert decision["target"] == target
    assert reason_part in decision["reason"]


@pytest.mark.parametrize(
    ("name", "confidence", "predictor_retries", "expects_review"),
    [
        ("confident_prediction", 0.90, 0, False),
        ("low_confidence_before_exhaustion", 0.20, 2, False),
        ("low_confidence_after_exhaustion", 0.20, 3, True),
    ],
)
def test_human_review_policy_after_predictor_exhaustion(name, confidence, predictor_retries, expects_review):
    state = create_prediction_state("CCO", {}, "Oxidation")
    state.update({
        "confidence": confidence,
        "validation_results": {"product_validation": True, "mechanism_validation": True, "retrieved_context_validation": True},
        "validation_scores": {"mechanism_score": 0.8, "context_score": 0.8},
        "retry_count": {"predictor": predictor_retries, "retriever": 0, "verifier": 0, "workflow": predictor_retries},
    })
    decision = require_post_prediction_review(state)
    assert decision["interrupt"] is expects_review, name
    if expects_review:
        assert decision["reason"] == "low_confidence"


def test_predictor_sends_original_smiles_and_conditions(monkeypatch: pytest.MonkeyPatch):
    """The remote model receives original user input and selected conditions."""
    monkeypatch.setenv("MODEL_ENDPOINT", "https://example.invalid")
    response = {"success": True, "prediction": "N#CCC", "confidence": 0.87}
    fake = Mock()
    fake.predict.return_value = response
    received_requests = []

    def fake_predictor(request):
        received_requests.append(request)
        return fake

    monkeypatch.setattr("agents.predictor.ReactionPredictor", fake_predictor)
    state = create_prediction_state("CCBr.[Na+].[C-]#N", {"solvent": "DMF"}, "SN2")
    state["canonical_smiles"] = "N#[C-].CCBr.[Na+]"
    result = predict_reaction(state)
    assert result["prediction"] == "N#CCC"
    request = received_requests[0]
    assert request["original_smiles"] == "CCBr.[Na+].[C-]#N"
    assert request["conditions"] == {"solvent": "DMF"}


def test_local_pdf_fixture_is_a_real_extractable_document():
    """A document-grounded test uses the supplied local PDF fixture."""
    from pypdf import PdfReader

    assert PDF_FIXTURE.is_file()
    text = "".join(page.extract_text() or "" for page in PdfReader(str(PDF_FIXTURE)).pages)
    assert "SN2" in text
    assert "DMF" in text
