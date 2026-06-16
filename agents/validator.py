
from unittest import result

from utils.schemas_chat import ReactionState as State
from tools.chemistry import RDKit_tool

def validate_agent(state:State):
    smiles = state["smiles"]
    
    result = RDKit_tool.validate_smiles(smiles)
    
    return {
        "validation" : result["is_valid"],
        "warnings" :  result["errors"] + result["warnings"],
        "canonical_smiles" : result["canonical_smiles"] 
    }
    
#  check for the condition
def check_conditions(state: State):
    Condition=state["conditions"]
    pass