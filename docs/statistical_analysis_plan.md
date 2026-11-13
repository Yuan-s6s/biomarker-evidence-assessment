# Statistical Analysis Plan

## Scope

The current phase assesses one submitted gene/protein identifier against user-supplied, analysis-ready expression cohorts. It supports retrospective diagnostic tumour-versus-normal expression and prognostic overall-survival association. It does not perform locked-model external validation.

## Primary Questions

1. Is continuous biomarker expression different between tumour and normal specimens?
2. Is continuous biomarker expression associated with overall survival after adjustment for prespecified clinical covariates?
3. What is the apparent same-cohort change in concordance after adding biomarker expression to a baseline survival model?

## Inputs

Required input is `biomarker_id` plus one or more contexts of use. Incomplete context fields are reported as partial rather than silently converted into a complete clinical claim. Cohorts must provide separate metadata and expression CSV files.

## Diagnostic Analysis

Expression is analysed as a continuous variable. The MVP reports group means, mean difference, a normal-approximation 95% confidence interval, a Welch-style test statistic, a normal-approximation p-value, and rank-based ROC AUC. Adjacent normal tissue is labelled as comparator tissue and is not treated as healthy tissue by default.

## Prognostic Analysis

Survival analysis uses a deterministic Cox partial-likelihood implementation for fixed simulated and small local datasets. Expression remains continuous by default. Covariates are prespecified in the request; categorical covariates are encoded within each analysed cohort. The implementation reports coefficients, hazard ratios, standard errors, confidence intervals, and apparent concordance index. It does not freeze and transport discovery coefficients or encoding to external data.

## Robustness

The MVP performs fixed-seed bootstrap resampling of diagnostic effect direction. This is a limited sign-stability check, not optimism-corrected model validation. Future phases should add fit-for-purpose sample-size calculations, permutation tests, proportional-hazards diagnostics, restricted cubic splines, multiple-imputation sensitivity, calibration, and centre/batch/purity sensitivity.

## Cut-off Policy

No expression threshold is selected in the current workflow. If a future workflow estimates a cut-off, it must be selected in discovery data only and locked before external validation.

## Evidence Boundaries

The system may report retrospective association and, when all explicit gates pass, independent association replication. Per-cohort model refitting and same-cohort C-index differences must not be labelled external model validation or clinical utility. The system must not state that a biomarker is clinically validated, causal, or treatment-directing from this evidence alone.
