# Data Dictionary

## Metadata CSV

Required columns:

- `sample_id`: unique sample identifier.
- `diagnosis`: `tumor` or `normal`.

Optional columns:

- `survival_time`: positive follow-up time.
- `event`: `1` for event, `0` for censored.
- Requested covariates such as `age`, `sex`, and `stage`.

## Expression CSV

Required columns:

- `sample_id`: unique sample identifier matching metadata.
- One or more entity columns using a canonical symbol, alias, Ensembl ID, Entrez ID, or UniProt accession.

All expression values used for analysis must be numeric and analysis-ready.
