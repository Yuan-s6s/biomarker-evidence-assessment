# Evidence Grading

Evidence dimensions are scored independently from deterministic result fields. There is no opaque aggregate score.

- ID certainty: uniqueness and traceability of entity mapping.
- Technical reliability: data and assay quality as indicated by blocking QC and warnings.
- Independent replication: availability and direction concordance across discovery and external cohorts.
- Statistical robustness: bootstrap and sensitivity-analysis stability.
- Orthogonal support: RNA/protein concordance when protein data are supplied.
- Incremental clinical value: improvement over a baseline clinical model.
- Transportability: cross-platform, centre, and population evidence.

Overall grades are rule-based labels:

- A: strong virtual evidence; prioritise prospective or experimental validation.
- B: substantial evidence with a clearly defined missing component.
- C: promising but unstable or supported by limited external evidence.
- D: insufficient evidence.
- E: conflicting evidence or a high likelihood of false positivity.

Phase 1 defaults to conservative grades because it uses local retrospective data and has no external database connection.
