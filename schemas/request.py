from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    """
    Incoming request from Swagger/UI.
    """

    reactants: str = Field(
        ...,
        description="Reaction SMILES"
    )

    mechanism: str = Field(
        ...,
        description="Reaction mechanism (SN1, SN2, Oxidation...)"
    )

    conditions: Dict[str, Any] = Field(
        default_factory=dict
    )

    pdf_context: List[str] = Field(
        default_factory=list
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict
    )

    user_id: Optional[str] = Field(
        default=None,
        description="User ID for document ownership"
    )
