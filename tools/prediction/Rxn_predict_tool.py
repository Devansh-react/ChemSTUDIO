from typing import List, Dict
from datetime import datetime


class ReactionPredictor:

    def __init__(
        self,
        smiles: str,
        conditions: Dict[str, str],
        canonical_smiles: str,
        retrieved_context: List[Dict]
    ):
        self.smiles = smiles
        self.conditions = conditions
        self.canonical_smiles = canonical_smiles
        self.retrieved_context = retrieved_context

    # ---------------------------
    # Prepare inputs
    # ---------------------------
    def preprocess(self):

        processed_input = {
            "smiles":
                self.canonical_smiles
                or self.smiles,

            "conditions":
                self.conditions,

            "retrieved_context":
                self.retrieved_context
        }

        return processed_input

    # ---------------------------
    # Build model prompt/payload
    # ---------------------------
    def build_prompt(
        self,
        processed_input: Dict
    ):

        prompt = f"""
        Reaction Prediction

        Reactant:
        {processed_input["smiles"]}

        Conditions:
        {processed_input["conditions"]}

        Context:
        {processed_input["retrieved_context"]}
        """

        return prompt

    # ---------------------------
    # Model Call
    # Replace later with
    # API call / ReactionT5
    # ---------------------------
    def call_model(
        self,
        prompt: str
    ):

        return {
            "prediction":
                "Predicted Reaction Class",

            "confidence":
                0.85,

            "mechanism":
                "Mechanism"
        }

    # ---------------------------
    # Output Formatting
    # ---------------------------
    def postprocess(
        self,
        model_output: Dict
    ):

        prediction = model_output[
            "prediction"
        ]

        confidence = model_output[
            "confidence"
        ]

        mechanism = model_output[
            "mechanism"
        ]

        prediction_metadata = {

            "model_name":
                "T5-v1.0",

            "model_version":
                "V1.0",

            "timestamp":
                datetime.now().isoformat(),

            "confidence_score":
                confidence,

            "used_external_context":
                len(
                    self.retrieved_context
                ) > 0
        }

        return {
            "prediction":
                prediction,

            "confidence":
                confidence,

            "mechanism":
                mechanism,

            "prediction_metadata":
                prediction_metadata
        }

    # ---------------------------
    # Main Pipeline
    # ---------------------------
    def predict(self):

        processed_input = (
            self.preprocess()
        )

        prompt = self.build_prompt(
            processed_input
        )

        model_output = (
            self.call_model(prompt)
        )

        final_output = (
            self.postprocess(
                model_output
            )
        )

        return final_output