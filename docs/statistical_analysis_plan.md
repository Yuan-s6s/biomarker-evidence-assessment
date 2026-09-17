# Statistical Analysis Plan

## Scope

Phase 1 validates one submitted gene/protein identifier against user-supplied, analysis-ready expression cohorts. It supports diagnostic tumour-versus-normal expression and prognostic overall-survival association.

## Primary Questions

1. Is continuous biomarker expression different between tumour and normal specimens?
2. Is continuous biomarker expression associated with overall survival after adjustment for prespecified clinical covariates?
3. Does adding biomarker expression improve a baseline clinical survival model?

## Inputs

Required input is `biomarker_id`. Missing disease, intended use, specimen, endpoint, and covariate fields are recorded as system assumptions. Cohorts must provide separate metadata and expression CSV files.

## Diagnostic Analysis

Expression is analysed as a continuous variable. The MVP reports group means, mean difference, a normal-approximation 95% confidence interval, a Welch-style test statistic, a normal-approximation p-value, and rank-based ROC AUC. Adjacent normal tissue is labelled as comparator tissue and is not treated as healthy tissue by default.

## Prognostic Analysis

Survival analysis uses a deterministic Cox partial-likelihood implementation for fixed simulated and small local datasets. Expression remains continuous by default. Covariates are prespecified in the request; categorical covariates are dummy encoded from training/discovery values. The implementation reports coefficients, hazard ratios, standard errors, confidence intervals, and concordance index.

## Robustness

The MVP performs fixed-seed bootstrap resampling for diagnostic mean difference stability and a covariate-sensitivity Cox model. Future phases should add permutation tests, proportional-hazards diagnostics, restricted cubic splines, missing-data sensitivity, and centre/batch/purity sensitivity.

## Cut-off Policy

No expression threshold is selected in Phase 1. If a future workflow estimates a cut-off, it must be selected in discovery data only and locked before external validation.

## Evidence Boundaries

The system may report retrospective association and prediction evidence. It must not state that a biomarker is clinically validated, causal, or treatment-directing from this evidence alone.
