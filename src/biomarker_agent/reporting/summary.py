from __future__ import annotations

from biomarker_agent.schemas import ExternalEvidenceResult, ExternalReportSummary


def _counted(count: int, singular: str, plural: str | None = None) -> str:
    label = singular if count == 1 else plural or f"{singular}s"
    return f"{count} {label}"


def build_external_report_summary(result: ExternalEvidenceResult) -> ExternalReportSummary:
    """Build a deterministic summary exclusively from validated result fields."""
    entity_name = result.entity.hgnc_symbol or result.entity.query
    stage = result.evidence_conclusion.stage.replace("_", " ")
    flow = result.literature_summary

    if result.entity.resolution_confidence == "unique":
        identity_finding = f"The submitted biomarker resolved uniquely to {entity_name}."
    else:
        identity_finding = (
            f"Biomarker identity resolution is {result.entity.resolution_confidence}; "
            "downstream interpretation remains limited."
        )

    if flow.retrieval_warnings and flow.total_hits == 0 and flow.records_retrieved == 0:
        retrieval_finding = (
            "PubMed retrieval did not complete, so no interpretable total-hit count or article set was obtained."
        )
    else:
        retrieved_verb = "was" if flow.records_retrieved == 1 else "were"
        retrieval_finding = (
            f"PubMed reported {_counted(flow.total_hits, 'query hit')}; "
            f"{_counted(flow.records_retrieved, 'unique record')} {retrieved_verb} retrieved across "
            f"{_counted(flow.pages_fetched, 'page')}."
        )

    screening_finding = (
        f"Automated title/abstract screening processed {_counted(flow.records_screened, 'record')}: "
        f"{_counted(flow.records_included, 'included candidate')}, "
        f"{_counted(flow.records_excluded, 'excluded record')}, and "
        f"{_counted(flow.records_uncertain, 'uncertain record')}."
    )
    if flow.records_with_effect_estimates == 0:
        effect_finding = (
            "No retrieved article contained a rule-parsed, same-sentence biomarker effect estimate with a 95% "
            "confidence interval; no candidate estimates were extracted."
        )
    else:
        extraction_verb = "was" if flow.effect_estimates_extracted == 1 else "were"
        effect_finding = (
            f"{_counted(flow.records_with_effect_estimates, 'article')} contained at least one rule-parsed, "
            "same-sentence biomarker effect estimate with a 95% confidence interval; "
            f"{_counted(flow.effect_estimates_extracted, 'candidate estimate')} {extraction_verb} extracted."
        )

    if flow.truncated:
        completeness_finding = (
            f"Retrieval was truncated after {flow.records_retrieved} of {_counted(flow.total_hits, 'hit')}; "
            "the retrieved records are not a complete literature set."
        )
    elif flow.retrieval_warnings:
        completeness_finding = (
            f"Retrieval generated {_counted(len(flow.retrieval_warnings), 'warning')}; completeness cannot be assumed."
        )
    else:
        completeness_finding = "Retrieval completed without pagination warnings and was not marked truncated."

    key_findings = [
        identity_finding,
        retrieval_finding,
        screening_finding,
        effect_finding,
        completeness_finding,
    ]
    if context_domain := result.evidence_domains.get("context_of_use"):
        key_findings.append(f"Context-of-use specification was assessed as {context_domain.status.replace('_', ' ')}.")

    return ExternalReportSummary(
        headline=(f"Assessment of {entity_name} in {result.disease}: the highest supported evidence stage is {stage}."),
        key_findings=key_findings,
        supported_claim=result.evidence_conclusion.supported_claim,
        interpretation_boundary=(
            "This summary describes literature retrieval and automated triage. It does not establish a "
            "validated association, independent replication, causality, analytical validity, or clinical utility; "
            "every candidate effect estimate requires full-text verification."
        ),
        priority_next_steps=result.evidence_conclusion.unmet_requirements[:3],
    )
