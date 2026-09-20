import os
from datetime import datetime
from typing import Any, Dict

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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

        self.base_url = os.getenv("MODEL_ENDPOINT", "").rstrip("/")

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
        retry_policy = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
        )
        adapter = HTTPAdapter(max_retries=retry_policy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # The deployed service exposes inference at /predict. A health route
        # is optional and must not prevent valid prediction requests.
        self.predict_endpoint = f"{self.base_url}/predict"

    # --------------------------------------------------
    # Health Check
    # --------------------------------------------------

    def check_health(self) -> bool:
        """Return whether an optional `/health` endpoint is available."""

        health_url = f"{self.base_url}/health"

        try:
            response = self.session.get(
                health_url,
                timeout=10
            )
            return response.ok

        except requests.RequestException:
            return False
 
    # --------------------------------------------------
    # Build Payload
    # --------------------------------------------------

    def build_model_input(self) -> Dict[str, Any]:

        payload = {
            "reactants": self.request["canonical_smiles"],
            "mechanism": self.request["mechanism"],
        }

        conditions = self.request.get("conditions", {})

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

            value = self.request.get(field, conditions.get(field))

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
                    ),
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
