from typing import Any, Dict, Optional, List


from pydantic import BaseModel, Field


class PredictionResponse(BaseModel):

    success: bool
    prediction: Optional[str]
    mechanism: Optional[str]
    explanation: Optional[str]
    verification: Optional[Dict]
    metadata: Dict[str, Any]

    warnings: List[str] = []