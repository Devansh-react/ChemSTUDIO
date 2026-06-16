from utils.schemas_chat import ReactionState as State
from tools.prediction.Rxn_predict_tool import ReactionPredictor

def predict_reaction(state:State):
    smiles = state.get("smiles")
    canonical_smiles = state.get("canonical_smiles") or ""
    conditions = state.get("conditions",{})
    retrieved_context = state.get("retrieved_context",[])
    if not retrieved_context:
        retrieved_context = []
        
    
    # this is the business logic of predictig the reaction calssify the mechnism and cal the confidence4
    
    predictor = ReactionPredictor(smiles = smiles, conditions = conditions, canonical_smiles = canonical_smiles, retrieved_context = retrieved_context)
    
    prediction_result = predictor.predict()
    
    return {
        "prediction": prediction_result.get("prediction"),
        "confidence": prediction_result.get("confidence") or 0.0,
        "mechanism": prediction_result.get("mechanism"),
        "prediction_metadata": prediction_result.get("prediction_metadata")
    }
    
    
    
