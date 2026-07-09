from agents.validator import validate_agent as Validator
from agents.retriever import retriever_agent as Reteriver_Agent
from agents.explainer import explainer_agent as explainer
from agents.predictor import predict_reaction as predictor
from agents.verifier import verifier_agent as verifier
from agents.pre_review import pre_review_agent

from prompts import (
    Validator_prompt,
    Retriever_prompt,
    prediction_prompt,
    verifier_prompt,
)

from tools.retrieval.RAG_tool import (
    retrieve_context as simlarity_search,
    retrieve_context_mmr as mmr_search,
)

from tools.chemistry import RDKit_tool
from tools.prediction.Rxn_predict_tool import ReactionPredictor
from tools.verification.Context_verifier import (
    verify_prediction_with_context as context_verifier,
)
from tools.verification.mechaism_verifier import validate_mechanism
from tools.Human_in_loop.human_review import human_review_agent

from middleware.limits import (
    tool_middleware as limits,
    Model_middleware as model,
)

from middleware.post_review import require_post_prediction_review
from middleware.retry import should_retry_prediction


AGENT_REGISTRY = {

    "validator": {
        "description": "Validates and canonicalizes the input SMILES.",
        "callable": Validator,
        "prompt": Validator_prompt,
        "tools": [
            RDKit_tool
        ],
        "middleware": [
            {
                "name": "tool_limit",
                "position": "before",
                "callable": limits
            }
        ]
    },

    "retriever": {
        "description": "Retrieves supporting context from uploaded literature.",
        "callable": Reteriver_Agent,
        "prompt": Retriever_prompt,
        "tools": [
            simlarity_search,
            mmr_search
        ],
        "middleware": [
            {
                "name": "tool_limit",
                "position": "before",
                "callable": limits
            }
        ]
    },

    "pre_review": {
        "description": "Mandatory review before prediction.",
        "callable": pre_review_agent,
        "prompt": "",
        "tools": [],
        "middleware": []
    },

    "predictor": {
        "description": "Predicts reaction products and mechanism.",
        "callable": predictor,
        "prompt": prediction_prompt,
        "tools": [
            ReactionPredictor
        ],
        "middleware": [
            {
                "name": "model_limit",
                "position": "before",
                "callable": model
            }
        ]
    },

    "verifier": {
        "description": "Validates predicted product, mechanism and retrieved context.",
        "callable": verifier,
        "prompt": verifier_prompt,
        "tools": [
            RDKit_tool,
            context_verifier,
            validate_mechanism
        ],
        "middleware": [
            {
                "name": "retry",
                "position": "after",
                "callable": should_retry_prediction
            },
            {
                "name": "post_review",
                "position": "after",
                "callable": require_post_prediction_review
            }
        ]
    },

    "explainer": {
        "description": "Generates the final explanation and report.",
        "callable": explainer,
        "prompt": "",
        "tools": [],
        "middleware": [
            {
                "name": "model_limit",
                "position": "before",
                "callable": model
            }
        ]
    },

    "human_review": {
        "description": "Collects user feedback after automatic retries fail.",
        "callable": human_review_agent,
        "prompt": "",
        "tools": [],
        "middleware": []
    },
    

}