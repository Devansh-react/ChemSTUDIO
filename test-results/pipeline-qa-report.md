# Chem Process Studio Pipeline QA Report

Generated: 2026-10-08T07:52:31.035783+00:00

## Result

- Total: 26
- Passed: 26
- Failed: 0
- Execution mode: deterministic component and orchestration QA; remote prediction service is mocked

## Evidence and scope

The suite validates every test input before the external model boundary. Predictor responses are deterministic fakes, so failures identify a pipeline-policy regression rather than a remote service outage. The document tests use `D:\Chem_Procress_studio\test_literature.pdf`; it contains simple SN2/DMF findings and is parsed as a real PDF.

## Representative predictor exchange

- Input: reactants `CCBr.[Na+].[C-]#N`; mechanism `SN2`; solvent `DMF`.
- Canonical preview input: `N#[C-].CCBr.[Na+]`.
- Deterministic model output: product `N#CCC`; confidence `0.87`.
- This proves the outbound boundary preserves the original reactants and conditions. It is not a live-model quality claim.

## Case results

| Result | Test | What was checked | Failure detail |
| --- | --- | --- | --- |
| PASSED | `tests.test_pipeline_qa::test_smiles_validation_matrix[ethanol-CCO-True-CCO]` | Input validation and canonicalization before any model call. | - |
| PASSED | `tests.test_pipeline_qa::test_smiles_validation_matrix[ethyl_bromide-CCBr-True-CCBr]` | Input validation and canonicalization before any model call. | - |
| PASSED | `tests.test_pipeline_qa::test_smiles_validation_matrix[acetic_acid-CC(=O)O-True-CC(=O)O]` | Input validation and canonicalization before any model call. | - |
| PASSED | `tests.test_pipeline_qa::test_smiles_validation_matrix[benzene-c1ccccc1-True-c1ccccc1]` | Input validation and canonicalization before any model call. | - |
| PASSED | `tests.test_pipeline_qa::test_smiles_validation_matrix[dot_separated_reactants-CCBr.[Na+].[C-]#N-True-None]` | Input validation and canonicalization before any model call. | - |
| PASSED | `tests.test_pipeline_qa::test_smiles_validation_matrix[charged_reactant-C[N+](C)(C)C-True-C[N+](C)(C)C]` | Input validation and canonicalization before any model call. | - |
| PASSED | `tests.test_pipeline_qa::test_smiles_validation_matrix[invalid_plain_text-not a smiles-False-None]` | Input validation and canonicalization before any model call. | - |
| PASSED | `tests.test_pipeline_qa::test_smiles_validation_matrix[invalid_unclosed_ring-C1CC-False-None]` | Input validation and canonicalization before any model call. | - |
| PASSED | `tests.test_pipeline_qa::test_smiles_validation_matrix[invalid_unclosed_branch-CC(-False-None]` | Input validation and canonicalization before any model call. | - |
| PASSED | `tests.test_pipeline_qa::test_smiles_validation_matrix[invalid_element-Xx-False-None]` | Input validation and canonicalization before any model call. | - |
| PASSED | `tests.test_pipeline_qa::test_smiles_validation_matrix[empty_input--False-None]` | Input validation and canonicalization before any model call. | - |
| PASSED | `tests.test_pipeline_qa::test_smiles_validation_matrix[radical_rejected-[CH3]-False-None]` | Input validation and canonicalization before any model call. | - |
| PASSED | `tests.test_pipeline_qa::test_preview_contains_exact_predictor_context[no_pdf_minimal]` | Pre-prediction preview contains exact canonical SMILES, conditions, and literature context. | - |
| PASSED | `tests.test_pipeline_qa::test_preview_contains_exact_predictor_context[no_pdf_conditions]` | Pre-prediction preview contains exact canonical SMILES, conditions, and literature context. | - |
| PASSED | `tests.test_pipeline_qa::test_preview_contains_exact_predictor_context[pdf_grounded]` | Pre-prediction preview contains exact canonical SMILES, conditions, and literature context. | - |
| PASSED | `tests.test_pipeline_qa::test_retry_policy_matrix[low_confidence_first_attempt-{'confidence': 0.49}-True-predictor-Low confidence]` | Low confidence, validation failure, retriever retry, and retry-limit policies. | - |
| PASSED | `tests.test_pipeline_qa::test_retry_policy_matrix[low_confidence_second_attempt-{'confidence': 0.1, 'retry_count': {'predictor': 2, 'retriever': 0, 'verifier': 0, 'workflow': 2}}-True-predictor-Low confidence]` | Low confidence, validation failure, retriever retry, and retry-limit policies. | - |
| PASSED | `tests.test_pipeline_qa::test_retry_policy_matrix[low_confidence_exhausted-{'confidence': 0.1, 'retry_count': {'predictor': 3, 'retriever': 0, 'verifier': 0, 'workflow': 3}}-False-none-All validations]` | Low confidence, validation failure, retriever retry, and retry-limit policies. | - |
| PASSED | `tests.test_pipeline_qa::test_retry_policy_matrix[invalid_product-{'validation_results': {'product_validation': False}}-True-predictor-Product validation failed]` | Low confidence, validation failure, retriever retry, and retry-limit policies. | - |
| PASSED | `tests.test_pipeline_qa::test_retry_policy_matrix[invalid_context-{'validation_results': {'retrieved_context_validation': False}}-True-retriever-Retrieved context validation failed]` | Low confidence, validation failure, retriever retry, and retry-limit policies. | - |
| PASSED | `tests.test_pipeline_qa::test_retry_policy_matrix[workflow_limit-{'retry_count': {'predictor': 0, 'retriever': 0, 'verifier': 0, 'workflow': 5}}-False-none-Maximum workflow]` | Low confidence, validation failure, retriever retry, and retry-limit policies. | - |
| PASSED | `tests.test_pipeline_qa::test_human_review_policy_after_predictor_exhaustion[confident_prediction-0.9-0-False]` | Human review recommendation after predictor retries are exhausted. | - |
| PASSED | `tests.test_pipeline_qa::test_human_review_policy_after_predictor_exhaustion[low_confidence_before_exhaustion-0.2-2-False]` | Human review recommendation after predictor retries are exhausted. | - |
| PASSED | `tests.test_pipeline_qa::test_human_review_policy_after_predictor_exhaustion[low_confidence_after_exhaustion-0.2-3-True]` | Human review recommendation after predictor retries are exhausted. | - |
| PASSED | `tests.test_pipeline_qa::test_predictor_sends_original_smiles_and_conditions` | Outbound predictor payload preserves original SMILES and conditions. | - |
| PASSED | `tests.test_pipeline_qa::test_local_pdf_fixture_is_a_real_extractable_document` | PDF fixture is readable and supplies SN2/DMF evidence. | - |

## Interpretation

A passing pre-review case proves that the preview payload contains the exact canonical SMILES, conditions, warnings, and retrieved evidence available immediately before prediction. A passing exhausted-low-confidence case proves the policy raises a post-prediction human-review recommendation after three predictor retries. This is a policy-level test: API calls intentionally set `skip_human_review=True`, so API clients receive a warning rather than an interactive interrupt.

## Run output

```text
..........................                                               [100%]
26 passed in 1.56s

```
