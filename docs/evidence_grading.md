# Evidence Conclusions

The primary conclusion is the highest evidence stage supported by completed,
auditable checks. It is not a probability that the biomarker works.

## Domain Status

Each evidence domain is reported independently:

- `supported`: the implemented requirements for this domain were met.
- `partial`: some evidence exists, but one or more required gates are missing.
- `concern`: a quality or applicability problem was detected.
- `conflicting`: eligible results disagree.
- `not_evaluated`: the workflow did not assess the domain. This is not evidence against the biomarker.

Domains include identity, context of use, structural data quality,
retrospective association, independent replication, locked external model
validation, analytical validity, and clinical utility.

## Evidence Stages

Stages are deliberately claim bounded:

1. `identity_confirmed`: identity only.
2. `literature_signal`: relevant PubMed title/abstract records retrieved, without full-text eligibility or risk-of-bias appraisal. Automated screening decisions and rule-parsed effect-and-95%-CI candidates remain unverified.
3. `retrospective_association`: an association estimated in supplied retrospective data.
4. `independent_association_replication`: a concordant, precise association passes documented replication gates.
5. `locked_external_model_validation`: a frozen model is applied unchanged in fit-for-purpose external data.
6. `prospective_clinical_utility`: prospective evidence shows beneficial decision or outcome impact.

The current implementation can automatically support stages 1-4. Stages 5
and 6 are reserved and must remain `not_evaluated` until those workflows are
implemented.

## Compatibility Indicators

The historical 0-5 `evidence_scores`, `overall_confidence`, and A-E
`overall_grade` fields remain for machine-readable backward compatibility.
They are uncalibrated heuristics, are not averaged into the evidence stage, and
must not be interpreted as clinical success probabilities. External metadata
retrieval can score at most one point for literature presence regardless of
publication count or retrieval limit.
