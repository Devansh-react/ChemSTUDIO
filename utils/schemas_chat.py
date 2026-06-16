from typing import TypedDict,List,Dict,Optional


class ReactionState(TypedDict):
    smiles:str
    canonical_smiles:Optional[str]
    conditions:Dict[str,str]    
    validation:bool
    
    uploaded_docs: Optional[List[str]]
    pdf_injested:bool
    external_doc_available:bool
    retrieved_context: List[Dict] 
    
    
    prediction:Optional[str]
    confidence:float
    mechanism:Optional[str]
    prediction_metadata:Optional[Dict[str,str]]
    
    
    warnings:List[str]
    messages:Optional[List[str]]
    
    