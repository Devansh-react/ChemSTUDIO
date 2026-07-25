import os
from datetime import datetime
from typing import Any, Dict

import requests
from dotenv import load_dotenv

load_dotenv()


class PredictionAPIError(Exception):
    """Base Prediction API Exception."""
    pass


class PredictionTimeoutError(PredictionAPIError):
    """Prediction API Timeout."""
    pass


class PredictionConnectionError(PredictionAPIError):
    """Prediction API Connection Error."""
    pass


class ReactionPredictor:
    """
    ChemStudio Reaction Prediction Tool

    Responsibilities
    ----------------
    ✓ Build prediction payload
    ✓ Call deployed model API
    ✓ Parse API response
    ✓ Return standardized prediction object

    Does NOT
    --------
    ✗ Validate SMILES
    ✗ Canonicalize molecules
    ✗ Verify chemistry
    ✗ Explain mechanisms
    ✗ Retrieve literature
    """

    def __init__(self, request: Dict[str, Any]):

        self.request = request

        self.base_url = os.getenv("MODEL_ENDPOINT")

        if not self.base_url:
            raise ValueError("MODEL_ENDPOINT not found.")

        self.model_name = os.getenv(
            "MODEL_NAME",
            "ChemStudio Reaction Predictor"
        )

        self.model_version = os.getenv(
            "MODEL_VERSION",
            "1.0"
        )

        self.timeout = int(
            os.getenv("MODEL_TIMEOUT", "60")
        )

        self.session = requests.Session()

        self.predict_endpoint = self._initialize_endpoint()

    # --------------------------------------------------
    # Health Check
    # --------------------------------------------------

    def _initialize_endpoint(self) -> str:

        health_url = f"{self.base_url}/health"

        try:

            response = self.session.get(
                health_url,
                timeout=10
            )

            response.raise_for_status()

        except requests.Timeout:

            raise PredictionTimeoutError(
                "Prediction API health check timed out."
            )

        except requests.RequestException as e:

            raise PredictionConnectionError(
                f"Unable to connect to Prediction API.\n{e}"
            )

        return f"{self.base_url}/predict"

    # --------------------------------------------------
    # Build Payload
    # --------------------------------------------------

    def build_model_input(self) -> Dict[str, Any]:

        payload = {

            "reactants":
                self.request["canonical_smiles"],

            "mechanism":
                self.request["mechanism"]
        }

        optional_fields = [

            "temperature",
            "pressure",
            "solvent",
            "catalyst",
            "time",
            "reagents",
            "metadata"
        ]

        for field in optional_fields:

            value = self.request.get(field)

            if value is not None:
                payload[field] = value

        return payload

    # --------------------------------------------------
    # Call Model
    # --------------------------------------------------

    def call_model(
        self,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:

        try:

            response = self.session.post(

                self.predict_endpoint,

                json=payload,

                timeout=self.timeout
            )

            response.raise_for_status()

            data = response.json()

            if not data.get("success", False):

                raise PredictionAPIError(

                    data.get(
                        "error",
                        "Prediction failed."
                    )
                )

            return data

        except requests.Timeout:

            raise PredictionTimeoutError(
                "Prediction API timed out."
            )

        except requests.RequestException as e:

            raise PredictionConnectionError(
                f"Prediction API request failed.\n{e}"
            )

    # --------------------------------------------------
    # Postprocess
    # --------------------------------------------------

    def postprocess(
        self,
        model_output: Dict[str, Any]
    ) -> Dict[str, Any]:

        return {

            "success": True,

            "prediction":
                model_output.get("prediction"),

            "mechanism":
                self.request.get("mechanism"),

            "error": None,

            "prediction_metadata": {

                "model":
                    self.model_name,

                "version":
                    self.model_version,

                "timestamp":
                    datetime.now().isoformat(),

                "used_external_context":
                    bool(
                        self.request.get(
                            "retrieved_context"
                        )
                    ),

                "conditions_provided":
                    bool(
                        self.request.get(
                            "conditions"
                        )
                    )
            }
        }

    # --------------------------------------------------
    # Main Prediction Pipeline
    # --------------------------------------------------

    def predict(self) -> Dict[str, Any]:

        payload = self.build_model_input()

        model_output = self.call_model(
            payload
        )

        return self.postprocess(
            model_output
        )

    # --------------------------------------------------
    # Cleanup
    # --------------------------------------------------

    def close(self):

        self.session.close()