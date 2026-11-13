# Data Dictionary

## Metadata CSV

Required for every workflow:

- `sample_id`: unique sample identifier.

Required for diagnostic analysis:

- `diagnosis`: `tumor` or `normal`.

Required for prognostic overall-survival analysis:

- `survival_time`: positive follow-up time.
- `event`: `1` for event, `0` for censored.

Optional columns:

- Requested covariates such as `age`, `sex`, and `stage`.

## Expression CSV

Required columns:

- `sample_id`: unique sample identifier matching metadata.
- One or more entity columns using a canonical symbol, alias, Ensembl ID, Entrez ID, or UniProt accession.

All expression values used for analysis must be numeric and analysis-ready.

## Context of Use

Each entry in `contexts_of_use` represents one claim. Relevant fields include:

- `category`: diagnostic, prognostic, predictive, monitoring, `susceptibility_risk`,
  `pharmacodynamic_response`, or safety.
- `disease`: unambiguous full disease name.
- `target_population` and `clinical_setting`.
- `specimen` and `assay`.
- `endpoint` plus `time_horizon` for prognostic claims.
- `reference_standard` for diagnostic claims.
- `intervention` for predictive or response claims.
- `baseline_comparator` and `intended_action`.

Missing fields produce a `partial` context-of-use status rather than being
silently inferred.

Every context disease must match the request-level disease. Use one canonical,
unambiguous disease name throughout a request.

## External Cohort Documentation

An external cohort is not counted as independent replication merely because its
role is named `external`. The configuration must document:

- `disease`: must match the assessed disease scope.
- `independent_from_discovery: true`.
- `protocol_locked: true`.
- `sample_size_justification`: a reproducible precision or sample-size rationale.

The observed external result must also be directionally concordant, have a
confidence interval excluding the null, and have no automated imprecision or
instability warning. These gates support association replication only. They do
not constitute locked-model external validation.

The configuration rejects reversed cohort roles, duplicate cohort names, and
reuse of a discovery expression or metadata file as an external cohort input.
