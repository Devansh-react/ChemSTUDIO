from dataclasses import dataclass

from utils.schema import ReactionState as State

from tools.chemistry.RDKit_tool import (
    validate_smiles
)

from tools.verification.Context_verifier import (
    verify_prediction_with_context
)

from tools.verification.mechaism_verifier import (
    validate_mechanism
)


@dataclass
class ValidationResults:
    smiles_validation: bool = False
    retrieved_context_validation: bool = False
    mechanism_validation: bool = False


def verifier_agent(state: State):

    validation = ValidationResults()

    context_score = 0.0
    mechanism_score = 0.0

    # ==========================
    # Prediction Validation
    # ==========================
    output = state.get(
        "prediction",
        ""
    )

    if not output:

        return {
            "validation_results": {
                "product_validation": False,
                "retrieved_context_validation": False,
                "mechanism_validation": False
            },
            "validation_scores": {
                "context_score": 0.0,
                "mechanism_score": 0.0
            },

        }

    # ==========================
    # RDKit Validation
    # ==========================
    rdkit_result = validate_smiles(
        output
    )

    validation.smiles_validation = (
        rdkit_result.get(
            "is_valid",
            False
        )
    )

    # ==========================
    # Context Validation
    # ==========================
    prediction_mechanism = (
        state.get("mechanism")
        or ""
    )

    retrieved_context = state.get(
        "retrieved_context",
        []
    )

    confidence = state.get(
        "confidence",
        0.0
    )
    if not confidence:
        confidence = 0.0
    

    raw_score = (
        verify_prediction_with_context(
            prediction_mechanism,
            retrieved_context,
            confidence
        )
    )

    if isinstance(
        raw_score,
        (float, int)
    ):
        context_score = float(
            raw_score
        )

    validation.retrieved_context_validation = (
        context_score >= 0.25
    )

    # ==========================
    # Mechanism Validation
    # ==========================
    reactant = (
        state.get(
            "canonical_smiles"
        )
        or state.get(
            "smiles",
            ""
        )
    )

    conditions = state.get(
        "conditions",
        {}
    )

    raw_mechanism_score = (
        validate_mechanism(
            reactant,
            conditions,
            prediction_mechanism,
            output,
            retrieved_context
        )
    )

    if isinstance(
        raw_mechanism_score,
        (float, int)
    ):
        mechanism_score = float(
            raw_mechanism_score
        )

    validation.mechanism_validation = (
        mechanism_score >= 0.50
    )

    # ==========================
    # Return State Update
    # ==========================
    return {

        "validation_results": {

            "product_validation":
                validation.smiles_validation,

            "retrieved_context_validation":
                validation.retrieved_context_validation,

            "mechanism_validation":
                validation.mechanism_validation
        },

        "validation_scores": {

            "context_score":
                context_score,

            "mechanism_score":
                mechanism_score
        }
    }