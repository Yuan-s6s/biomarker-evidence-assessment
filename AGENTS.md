# Project instructions

## Goal
Build an auditable virtual validation system for RNA and protein expression biomarkers.

## Non-negotiable scientific rules
- Treat association, prediction, causality, and clinical utility as different claims.
- Never call a biomarker clinically validated from retrospective virtual evidence alone.
- Report effect sizes and confidence intervals; do not optimise for p-values.
- Never choose and evaluate a cut-off in the same validation dataset.
- Keep discovery and external-validation datasets strictly separated.
- Do not pool raw cross-platform expression values without a documented harmonisation plan.
- Record every cohort, endpoint, exclusion, transformation, covariate, and analysis attempt.
- LLM-generated text may interpret validated result objects but may not invent statistics or evidence scores.

## Engineering rules
- Use typed Pydantic schemas at module boundaries.
- Keep exploratory notebooks in notebooks/exploration_only; production logic belongs in src/.
- Add unit tests for every statistical utility and integration tests for each pipeline.
- Use fixed random seeds where relevant and record package versions.
- Run formatting, linting, type checking, and tests before declaring a task complete.

## Definition of done
- The requested behaviour is implemented.
- Tests pass.
- Scientific assumptions and limitations are documented.
- Outputs contain sufficient provenance to reproduce the result.
