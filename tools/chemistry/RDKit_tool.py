# contains the external RDKit that has all chemistry utility functions 
# https://www.rdkit.org/docs/GettingStartedInPython.html

from logging import warning
from rdkit import Chem
from rdkit.Chem import rdMolStandardize

MAX_ATOMS = 300


def validate_smiles(smiles:str):
    
    result = {
        "is_valid":False,
        "canonical_smiles":None,
        "errors":[],
        "warning":[],
        "mol":None
    }
     
    # Empty Input
    if not smiles.strip():
        result["errors"].append("Empty SMILES string.")
        
    # Syntax Validation
    mol = Chem.MolFromSmiles(smiles)
    
    if mol is None:
        result["errors"].append("Invalid SMILES syntax.")
        return result
    else:
        result["mol"] = mol
        # Canonicalization
        canonical_smiles = Chem.MolToSmiles(mol,True)
        result["canonical_smiles"] = canonical_smiles
    
    # MolStandardize Validation
    validation_errors = rdMolStandardize.ValidateSmiles(smiles)
    if validation_errors:
        result["errors"].extend(validation_errors)
        
    
    # Atom Count Check 
    if mol.GetNumAtoms() > MAX_ATOMS:
        result["errors"].append(
            f"Molecule exceeds maximum atom limit of {MAX_ATOMS}"
        )
    
    #  radical species -> freee radical atoms 
    for atom in mol.GetAtoms():
        count =atom.GetNumRadicalElectrons() 
        if count> 0:
            result["errors"].append(f"{count} Radical species found")
            
    # Sanitization Check :This catches many impossible structures.
    try:
        Chem.SanitizeMol(mol)
    except Exception as e:
        result["errors"].append(str(e))
        
    #  final validation 
    result["is_valid"] = len(result['errors']) == 0  


    
    
    # 7 validation checks 
