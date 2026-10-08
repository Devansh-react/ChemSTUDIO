"""Regression tests for the deterministic prediction workflow."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import Mock

import pytest

from agents.predictor import predict_reaction
from graph.state import create_prediction_state
from tools.prediction.Rxn_predict_tool import ReactionPredictor


def test_predictor_preserves_model_confidence(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MODEL_ENDPOINT", "https://model.example")
    predictor = ReactionPredictor(
        {
            "canonical_smiles": "CCO",
            "original_smiles": "CCO",
            "mechanism": "Oxidation",
        }
    )
    predictor.call_model = Mock(
        return_value={"success": True, "prediction": "CC=O", "confidence": "0.82"}
    )

    result = predictor.predict()

    assert result["prediction"] == "CC=O"
    assert result["confidence"] == 0.82
    predictor.close()


def test_predictor_returns_failed_state_when_model_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
):
    class UnavailablePredictor:
        def __init__(self, request):
            self.request = request

        def predict(self):
            from tools.prediction.Rxn_predict_tool import PredictionConnectionError

            raise PredictionConnectionError("connection refused")

        def close(self):
            pass

    monkeypatch.setattr("agents.predictor.ReactionPredictor", UnavailablePredictor)
    state = create_prediction_state("CCO", {}, "Oxidation")
    state["canonical_smiles"] = "CCO"

    result = predict_reaction(state)

    assert result["status"] == "failed"
    assert result["prediction"] is None
    assert "Prediction service unavailable" in result["warnings"][-1]


def test_invalid_smiles_stops_before_prediction():
    from agents.validator import validate_agent

    state = create_prediction_state("not a smiles", {}, "SN2")
    result = validate_agent(state)

    assert result["validation"] is False
    assert result["status"] == "failed"


def test_explained_workflow_completes_instead_of_looping():
    from agents.supervisor import SupervisorAgent

    state = create_prediction_state("CCO", {}, "Oxidation")
    cast(Any, state).update(
        {
            "status": "explained",
            "workflow_plan": ["validator", "explainer"],
            "workflow_index": 1,
            "next_agent": "explainer",
        }
    )

    result = SupervisorAgent()._supervisor_router(state)

    assert result.update["status"] == "completed"
    assert result.goto == "__end__"
