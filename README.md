# Biomarker Evidence Assessment Toolkit

An auditable command-line toolkit for assessing the evidence, reproducibility,
and validation readiness of RNA and protein expression biomarkers. Give it a
biomarker and disease to retrieve public identity and PubMed metadata, or
provide cohort CSV files to run deterministic statistical analyses.

## Why This Toolkit Exists

Finding a candidate expression biomarker is relatively easy; deciding whether
the supporting evidence is credible, reproducible, and ready for the next
validation step is much harder. Gene identity, literature, expression data,
clinical outcomes, and analysis decisions are often reviewed in separate tools
and then combined manually. That makes it easy to mistake a reported
association for independent validation or clinical utility.

This toolkit turns a biomarker question into a structured, auditable evidence
assessment. It does not return a simple "works" or "does not work" verdict.
Instead, it records what was checked, runs deterministic analyses when cohort
data are supplied, separates evidence dimensions, and makes missing evidence
explicit.

| Common problem | How the toolkit addresses it |
| --- | --- |
| Ambiguous or inconsistent gene identifiers | Resolves symbols and common database identifiers before assessing evidence |
| Literature and cohort results reviewed in isolation | Provides consistent workflows and structured reports for public metadata searches and local cohort analyses |
| Discovery results treated as external confirmation | Keeps discovery and external-validation cohorts separate and never pools their raw values |
| Conclusions driven mainly by p-values | Reports effect sizes, confidence intervals, discrimination, and robustness measures |
| Confidence scores with unclear meaning | Uses deterministic rules with per-dimension justifications and explicit evidence gaps |
| Analyses that are difficult to reproduce | Records inputs, cohort roles, assumptions, provenance, and machine-readable results |

> Research software only. A confidence label summarizes the evidence retrieved
> and analyses completed; it is **not** the probability that a biomarker works
> and does not establish clinical validity or utility.

## What It Does

```text
biomarker + disease
        |
        v
resolve gene identity (offline resolver + MyGene.info)
        |
        +--> search disease-specific PubMed records
        |        |
        |        v
        |    metadata-level evidence confidence
        |
        +--> optional cohort analysis
                 (discovery required; external optional)
                 |
                 v
             QC, effect sizes, Cox models, bootstrap checks
                 |
                 v
             reproducible JSON, Markdown, and HTML reports
```

The current release includes:

- Gene resolution for symbols, Ensembl IDs, Entrez IDs, and UniProt accessions.
- MyGene.info identity lookup and NCBI PubMed metadata search.
- Blocking quality-control checks for user-supplied cohort CSVs.
- Continuous-expression tumour-versus-normal analysis.
- Cox proportional-hazards analysis with prespecified covariates.
- Bootstrap directional stability and covariate sensitivity.
- Baseline-versus-biomarker concordance-index comparison.
- Machine-readable JSON plus human-readable Markdown and HTML reports.

## Quick Start

Python 3.11 or newer is required.

```bash
git clone https://github.com/Yuan-s6s/biomarker-evidence-assessment.git
cd biomarker-evidence-assessment
./run.sh demo
```

The first run creates a local `.venv`, installs the toolkit, and analyses the
bundled example data. Later runs start immediately. The example report is
written to `reports/example/report.html`. An internet connection is required
the first time so that Python can download the dependencies.

Run a public literature and database check:

```bash
./run.sh external TP53 --disease "breast cancer" --out reports/tp53_breast
```

The disease can be a full name or common abbreviation. Full disease names are
recommended because synonym expansion is currently limited.

Open `reports/tp53_breast/external_report.html` in a browser, or inspect the
machine-readable `external_evidence.json`.

HTML reports are self-contained and work offline. They provide a responsive,
print-friendly overview followed by the underlying evidence scores, cohort and
quality-control details, effect estimates with confidence intervals, model
terms, limitations, recommended next steps, and full run provenance. Sections
that do not apply to a workflow are omitted or clearly marked as unavailable.

## Choose A Workflow

### 1. External Evidence Search

Use this when you only have a biomarker and disease:

```bash
./run.sh external RAB38 --disease LSCC --retmax 10 --out reports/rab38_lscc
```

This contacts MyGene.info and NCBI PubMed. It assesses identity certainty and
the amount of disease-specific literature found. It does not inspect full text,
verify reported effect sizes, or reanalyse public expression matrices.

### 2. Interactive Confidence Check

Use the question-driven interface:

```bash
./run.sh guided --planning-only --out reports/planning
```

Or omit `--planning-only` to be asked whether discovery and external-validation
CSV files are available:

```bash
./run.sh
```

### 3. Reproducible Cohort Assessment

Edit `configs/example_request.yaml`, then run:

```bash
./run.sh cohort configs/example_request.yaml --out reports/example
```

The included fixture data let you try this workflow immediately. A discovery
cohort is required for this mode; independently analysed external-validation
cohorts are optional. Input column requirements are documented in
[docs/data_dictionary.md](docs/data_dictionary.md).

The original `biomarker-external`, `biomarker-confidence`, and
`biomarker-agent` commands remain available as compatibility aliases.

For manual installation or development, use the standard editable install:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
biomarker-assess --help
```

## Understanding Confidence

Confidence means **confidence in the available evidence package**, not model
accuracy and not a probability of future clinical success. The external mode
scores these dimensions independently from 0 to 5:

| Dimension | Meaning |
| --- | --- |
| ID certainty | How confidently the input maps to one biological entity |
| Database identity support | Whether an external gene record was retrieved |
| Direct literature support | Disease-specific records found in title metadata |
| Indirect literature support | Related records without direct disease-title matching |
| Statistical validation | Whether expression/outcome data were reanalysed |
| Clinical utility | Whether a biomarker improved a baseline clinical model |

Because external mode currently retrieves metadata rather than expression
matrices, its statistical-validation and clinical-utility scores remain zero.
See [docs/evidence_grading.md](docs/evidence_grading.md) for the grading rules and
[docs/statistical_analysis_plan.md](docs/statistical_analysis_plan.md) for the
analysis assumptions.

## Input Data

Expression CSV files use samples as rows and biomarkers as columns. Metadata
CSV files use one row per sample and include `sample_id`; diagnostic analysis
also needs `diagnosis`, while survival analysis needs `survival_time` and
`event` columns. The example configuration and fixtures show a complete
runnable layout.

Discovery and external-validation cohorts remain separate throughout the
pipeline. Cut-offs must not be selected and evaluated in the same validation
dataset, and raw cross-platform values must not be pooled without a documented
harmonisation plan.

## Development

```bash
python -m pip install -e ".[dev]"
ruff format --check src tests
ruff check src tests
mypy src
pytest
```

Tests use local fixtures and do not require network access. External-source
calls are mocked in unit tests.

Contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md). This project
is available under the [MIT License](LICENSE).
