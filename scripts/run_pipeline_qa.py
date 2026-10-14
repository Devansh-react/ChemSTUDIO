r"""Run the deterministic pipeline QA suite and create JSON + Markdown reports.

Usage (PowerShell):
    .\.venv\Scripts\python.exe scripts\run_pipeline_qa.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "test-results"
JUNIT = OUTPUT / "pipeline-qa-junit.xml"
JSON_REPORT = OUTPUT / "pipeline-qa-report.json"
MARKDOWN_REPORT = OUTPUT / "pipeline-qa-report.md"

SUITE_SCOPE = {
    "smiles_validation_matrix": "Input validation and canonicalization before any model call.",
    "preview_contains_exact_predictor_context": "Pre-prediction preview contains exact canonical SMILES, conditions, and literature context.",
    "retry_policy_matrix": "Low confidence, validation failure, retriever retry, and retry-limit policies.",
    "human_review_policy_after_predictor_exhaustion": "Human review recommendation after predictor retries are exhausted.",
    "predictor_sends_original_smiles_and_conditions": "Outbound predictor payload preserves original SMILES and conditions.",
    "local_pdf_fixture_is_a_real_extractable_document": "PDF fixture is readable and supplies SN2/DMF evidence.",
}


def classify_case(nodeid: str) -> str:
    for prefix, description in SUITE_SCOPE.items():
        if prefix in nodeid:
            return description
    return "Pipeline QA contract."


def main() -> int:
    OUTPUT.mkdir(exist_ok=True)
    command = [sys.executable, "-m", "pytest", "tests/test_pipeline_qa.py", "-q", f"--junitxml={JUNIT}"]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)

    root = ET.parse(JUNIT).getroot()
    cases = []
    for node in root.iter("testcase"):
        failure = node.find("failure") or node.find("error")
        status = "passed" if failure is None else "failed"
        cases.append({
            "id": f"{node.attrib.get('classname', '')}::{node.attrib.get('name', '')}",
            "area": classify_case(node.attrib.get("name", "")),
            "status": status,
            "duration_seconds": round(float(node.attrib.get("time", 0)), 3),
            "failure": failure.attrib.get("message", "") if failure is not None else None,
        })

    summary = {"passed": sum(c["status"] == "passed" for c in cases), "failed": sum(c["status"] == "failed" for c in cases), "total": len(cases)}
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "deterministic component and orchestration QA; remote prediction service is mocked",
        "document_fixture": {
            "path": str(ROOT / "test_literature.pdf"),
            "description": "Local one-page SN2/DMF retrieval fixture already provided by the project.",
            "source_note": "Replace or add a downloaded research PDF when internet access is available; the test asserts that the fixture is a valid, extractable PDF.",
        },
        "summary": summary,
        "representative_model_exchange": {
            "input": {
                "reactants": "CCBr.[Na+].[C-]#N",
                "mechanism": "SN2",
                "conditions": {"solvent": "DMF"},
            },
            "mocked_model_output": {"prediction": "N#CCC", "confidence": 0.87},
            "why_mocked": "This initial policy suite must be repeatable and must not send 26 requests to the configured external predictor.",
        },
        "cases": cases,
        "pytest_stdout": completed.stdout,
        "pytest_stderr": completed.stderr,
    }
    JSON_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    rows = "\n".join(f"| {case['status'].upper()} | `{case['id']}` | {case['area']} | {case['failure'] or '-'} |" for case in cases)
    markdown = f"""# Chem Process Studio Pipeline QA Report

Generated: {report['generated_at']}

## Result

- Total: {summary['total']}
- Passed: {summary['passed']}
- Failed: {summary['failed']}
- Execution mode: {report['mode']}

## Evidence and scope

The suite validates every test input before the external model boundary. Predictor responses are deterministic fakes, so failures identify a pipeline-policy regression rather than a remote service outage. The document tests use `{report['document_fixture']['path']}`; it contains simple SN2/DMF findings and is parsed as a real PDF.

## Representative predictor exchange

- Input: reactants `CCBr.[Na+].[C-]#N`; mechanism `SN2`; solvent `DMF`.
- Canonical preview input: `N#[C-].CCBr.[Na+]`.
- Deterministic model output: product `N#CCC`; confidence `0.87`.
- This proves the outbound boundary preserves the original reactants and conditions. It is not a live-model quality claim.

## Case results

| Result | Test | What was checked | Failure detail |
| --- | --- | --- | --- |
{rows}

## Interpretation

A passing pre-review case proves that the preview payload contains the exact canonical SMILES, conditions, warnings, and retrieved evidence available immediately before prediction. A passing exhausted-low-confidence case proves the policy raises a post-prediction human-review recommendation after three predictor retries. This is a policy-level test: API calls intentionally set `skip_human_review=True`, so API clients receive a warning rather than an interactive interrupt.

## Run output

```text
{completed.stdout}{completed.stderr}
```
"""
    MARKDOWN_REPORT.write_text(markdown, encoding="utf-8")
    print(f"Report: {MARKDOWN_REPORT}")
    print(f"Machine-readable report: {JSON_REPORT}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
