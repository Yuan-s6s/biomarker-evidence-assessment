# Contributing

Thank you for helping improve Biomarker Evidence Assessment Toolkit.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```

## Pull requests

- Keep statistical calculations deterministic and covered by unit tests.
- Use typed Pydantic models at module boundaries.
- Document cohort, endpoint, exclusion, transformation, and covariate choices.
- Keep discovery and external-validation data separate.
- Report effect sizes and confidence intervals rather than relying on p-values.
- Do not describe retrospective virtual evidence as clinical validation.
- Update user documentation when behavior or input formats change.

Please open an issue before proposing a large new data connector or statistical
workflow so its provenance, licensing, and scientific assumptions can be agreed
up front.
