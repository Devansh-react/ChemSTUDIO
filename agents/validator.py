
from utils.schema import ReactionState as State
from tools.chemistry import RDKit_tool

def validate_agent(state: State):
    """Validate input SMILES while preserving earlier workflow warnings."""
    
    smiles = state["smiles"]

    result = RDKit_tool.validate_smiles(smiles)

    validation_warnings = (
        result.get("errors", [])
        + result.get("warnings", result.get("warning", []))
    )

    return {
        "validation": result.get("is_valid", False),
        "warnings": state.get("warnings", []) + validation_warnings,
        "canonical_smiles": result.get("canonical_smiles"),
        "status": "validated",
    }

#  check for the condition
def check_conditions(state: State):
    Condition=state["conditions"]
    pass
