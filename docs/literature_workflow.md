# PubMed Literature Workflow

## Scope

The external workflow performs reproducible PubMed title/abstract retrieval and
automated candidate screening. It is a discovery and triage workflow, not a
systematic review, full-text eligibility assessment, meta-analysis, or clinical
validation process.

## Retrieval

1. Build a disease-specific query requiring the resolved biomarker symbol in
   the title or abstract.
2. Call PubMed ESearch with `usehistory=y` and `retmax=0` to record the complete
   hit count and create an Entrez History set.
3. Retrieve records from that fixed history set with paginated EFetch calls.
4. Parse titles, abstracts, journal names, publication dates, and PMIDs.
5. Deduplicate records by PMID.

The default retrieval cap is 500 records and the default page size is 100.
`--max-records 0` requests all available records up to PubMed ESearch's
10,000-record limit. Searches above that limit remain truncated and are reported
as such. The implementation sends sequential requests and observes NCBI's
published request-rate guidance. Set `NCBI_API_KEY` to use an API key without
writing it into report provenance.

Reference: [NCBI E-utilities documentation](https://www.ncbi.nlm.nih.gov/sites/books/NBK25499/).

## Reported Counts

- `total_hits`: records matching the PubMed query before the local retrieval cap.
- `records_retrieved`: unique PMID records successfully parsed from EFetch pages.
- `records_screened`: retrieved records receiving an automated decision.
- `records_included`: title/abstract candidates containing the biomarker,
  disease, and at least one relevance term.
- `records_excluded`: records missing one or more required concepts despite an
  available abstract.
- `records_uncertain`: records without enough metadata for an automated decision.
- `abstracts_available`: retrieved records containing abstract text.
- `records_with_effect_estimates`: records with at least one conservatively
  parsed same-sentence biomarker effect estimate paired with a 95% confidence interval.
- `effect_estimates_extracted`: total number of such candidates across records.

If an EFetch page fails, previously retrieved pages are retained, the run is
marked truncated, and `retrieval_warnings` records the failed page. A partial
retrieval must not be interpreted as a complete literature set.

“Included” always means **included by automated title/abstract screening as a
candidate**. It does not mean that a study passed full-text eligibility review.

## Automated Screening

A record is an `include_candidate` when its title and abstract together contain:

- the resolved biomarker symbol;
- one configured disease term or synonym; and
- a biomarker-relevance term such as expression, diagnostic, prognostic,
  predictive, survival, or outcome.

A record with an abstract is excluded if one of these concepts is absent. A
record without an abstract is marked uncertain when the title alone is
insufficient.

These rules do not determine population eligibility, specimen suitability,
assay comparability, endpoint validity, cohort independence, or risk of bias.

## Effect-Estimate Candidates

The rule-based parser currently recognizes these measures only when the
biomarker symbol, estimate, and 95% confidence interval occur in the same
abstract sentence:

- hazard ratio;
- odds ratio;
- risk ratio or relative risk;
- area under the ROC curve;
- concordance index.

P-values alone are ignored. Candidates with impossible ranges or an estimate
outside its reported interval are rejected. Parsed values are stored as
`EffectEstimateCandidate` objects, labelled as abstract-derived and unverified,
and never increase the evidence stage or legacy score.

Every candidate must be checked against the full article, tables, supplements,
analysis population, model specification, endpoint definition, and reporting
direction before scientific use. Same-sentence proximity reduces but cannot
eliminate treatment-effect or covariate-effect false positives. The current
workflow does not resolve multiple models per article or detect duplicated
patient cohorts across publications.

## Evidence Boundary

PubMed retrieval can support `literature_signal` only. It cannot by itself
support retrospective association, independent replication, analytical
validity, locked external model validation, or clinical utility.

NCBI data-use policies and disclaimers apply. Abstract text is processed
transiently and is not reproduced in generated reports.
