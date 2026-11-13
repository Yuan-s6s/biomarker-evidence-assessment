from __future__ import annotations

import json
from datetime import datetime
from html import escape
from typing import Any
from urllib.parse import urlparse

from biomarker_agent.schemas import (
    ContextOfUse,
    EvidenceDomainAssessment,
    EvidenceScore,
    ExternalEvidenceResult,
    ValidationResult,
)

REPORT_CSS = """
:root {
  --ink: #17211f;
  --muted: #5d6966;
  --line: #d8dfdc;
  --soft: #f3f6f4;
  --paper: #ffffff;
  --canvas: #eef2f0;
  --teal: #176b62;
  --teal-dark: #123f3a;
  --blue: #2f6f9f;
  --green: #2f7d5a;
  --amber: #a85f16;
  --red: #b63d3d;
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  background: var(--canvas);
  color: var(--ink);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 15px;
  line-height: 1.55;
}
a { color: #155d91; text-underline-offset: 2px; }
a:hover { color: #0d466f; }
code, .mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  overflow-wrap: anywhere;
}

.report-header {
  background: var(--teal-dark);
  color: #fff;
  border-bottom: 5px solid #d6a447;
}
.header-inner, .report-nav, .report-main, .report-footer {
  width: min(1180px, calc(100% - 40px));
  margin: 0 auto;
}
.header-inner { padding: 34px 0 30px; }
.eyebrow {
  margin: 0 0 7px;
  color: #b9ddd6;
  font-size: 12px;
  font-weight: 750;
  letter-spacing: 0;
  text-transform: uppercase;
}
.title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}
h1 {
  max-width: 820px;
  margin: 0;
  font-size: 32px;
  line-height: 1.15;
  letter-spacing: 0;
}
.header-lead {
  max-width: 820px;
  margin: 12px 0 0;
  color: #d9e8e5;
  font-size: 16px;
}
.status-block {
  min-width: 150px;
  padding: 12px 14px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.08);
}
.status-block span { display: block; color: #cde1dd; font-size: 11px; text-transform: uppercase; }
.status-block strong { display: block; margin-top: 2px; font-size: 22px; text-transform: capitalize; }
.header-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 22px;
  margin-top: 22px;
  color: #cde1dd;
  font-size: 13px;
}

.nav-band { background: var(--paper); border-bottom: 1px solid var(--line); }
.report-nav {
  display: flex;
  gap: 4px;
  overflow-x: auto;
  padding: 8px 0;
  scrollbar-width: thin;
}
.report-nav a {
  flex: 0 0 auto;
  padding: 7px 10px;
  border-radius: 4px;
  color: #34433f;
  font-size: 13px;
  font-weight: 650;
  text-decoration: none;
}
.report-nav a:hover { background: var(--soft); color: var(--teal); }

.report-main {
  margin-top: 22px;
  margin-bottom: 36px;
  background: var(--paper);
  border: 1px solid var(--line);
  box-shadow: 0 8px 22px rgba(23, 33, 31, 0.07);
}
.notice {
  margin: 0;
  padding: 14px 24px;
  border-bottom: 1px solid #e4c988;
  background: #fff8e8;
  color: #5c4615;
  font-size: 13px;
}
.report-section { padding: 28px 24px; border-bottom: 1px solid var(--line); }
.report-section:last-child { border-bottom: 0; }
.section-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 20px; }
h2 { margin: 0; color: #24332f; font-size: 21px; line-height: 1.25; letter-spacing: 0; }
h3 { margin: 24px 0 10px; color: #2b3a36; font-size: 16px; letter-spacing: 0; }
.section-intro { max-width: 820px; margin: 7px 0 18px; color: var(--muted); }

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.metric-grid + .metric-grid { margin-top: 10px; }
.metric {
  min-height: 92px;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fbfcfb;
}
.metric-label { display: block; color: var(--muted); font-size: 12px; font-weight: 650; }
.metric-value { display: block; margin-top: 5px; font-size: 21px; font-weight: 760; line-height: 1.2; overflow-wrap: anywhere; }
.metric-detail { display: block; margin-top: 5px; color: var(--muted); font-size: 12px; }

.kv-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0;
  margin: 0;
  border-top: 1px solid var(--line);
  border-left: 1px solid var(--line);
}
.kv-item { min-width: 0; padding: 12px 14px; border-right: 1px solid var(--line); border-bottom: 1px solid var(--line); }
.kv-item dt { color: var(--muted); font-size: 11px; font-weight: 700; text-transform: uppercase; }
.kv-item dd { margin: 4px 0 0; overflow-wrap: anywhere; }

.score-list { border-top: 1px solid var(--line); }
.score-row {
  display: grid;
  grid-template-columns: minmax(150px, 0.7fr) minmax(180px, 1fr) minmax(260px, 1.8fr);
  gap: 18px;
  align-items: center;
  padding: 14px 0;
  border-bottom: 1px solid var(--line);
}
.score-name { font-weight: 700; }
.score-track { height: 10px; overflow: hidden; border-radius: 5px; background: #e7ecea; }
.score-fill { height: 100%; border-radius: 5px; }
.score-value { margin-top: 4px; color: var(--muted); font-size: 12px; font-variant-numeric: tabular-nums; }
.score-why { color: #4f5d59; font-size: 13px; }
.tone-good { background: var(--green); }
.tone-info { background: var(--blue); }
.tone-watch { background: var(--amber); }
.tone-danger { background: var(--red); }

.table-wrap { width: 100%; overflow-x: auto; border: 1px solid var(--line); }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
th { background: #edf3f0; color: #34433f; font-size: 11px; text-transform: uppercase; white-space: nowrap; }
tbody tr:last-child td { border-bottom: 0; }
tbody tr:hover { background: #fafcfb; }
.number { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }

.tag {
  display: inline-block;
  padding: 2px 7px;
  border: 1px solid currentColor;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 750;
  line-height: 1.45;
  text-transform: capitalize;
  white-space: nowrap;
}
.tag-good { color: #246345; background: #edf8f1; }
.tag-info { color: #245d83; background: #edf5fa; }
.tag-watch { color: #875015; background: #fff6e8; }
.tag-danger { color: #983838; background: #fff0f0; }
.tag-neutral { color: #55625f; background: #f3f5f4; }

.message-list, .plain-list { margin: 0; padding: 0; list-style: none; }
.message-list li, .plain-list li { position: relative; margin: 8px 0; padding-left: 17px; }
.message-list li::before, .plain-list li::before { content: ""; position: absolute; left: 0; top: 0.65em; width: 6px; height: 6px; border-radius: 50%; background: var(--teal); }
.message-list.warning li::before { background: var(--amber); }
.message-list.danger li::before { background: var(--red); }
.empty-state { padding: 18px; border: 1px dashed #b8c4c0; background: #fafcfb; color: var(--muted); }
.query-block { margin: 0 0 18px; padding: 13px 15px; border-left: 4px solid var(--blue); background: #f1f6f9; overflow-wrap: anywhere; }
.model-block + .model-block, .literature-item + .literature-item { margin-top: 22px; padding-top: 22px; border-top: 1px solid var(--line); }
.subhead-meta { display: flex; flex-wrap: wrap; gap: 8px 16px; margin: -4px 0 12px; color: var(--muted); font-size: 12px; }
.literature-title { margin: 0 0 6px; font-size: 15px; font-weight: 700; }
.literature-meta { display: flex; flex-wrap: wrap; gap: 7px 14px; color: var(--muted); font-size: 12px; }
.callout { margin-top: 14px; padding: 12px 14px; border-left: 4px solid var(--amber); background: #fff8e8; color: #5c4615; }
.claim-panel { margin: 18px 0 0; padding: 16px; border-left: 4px solid var(--blue); background: #f1f6f9; }
.claim-panel strong { display: block; margin-bottom: 5px; color: #244c67; }
.claim-panel p { margin: 0; }

.report-footer { padding: 0 0 34px; color: var(--muted); font-size: 12px; }

@media (max-width: 820px) {
  .header-inner, .report-nav, .report-main, .report-footer { width: min(100% - 24px, 1180px); }
  .title-row { display: block; }
  .status-block { width: fit-content; margin-top: 18px; }
  .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .kv-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .score-row { grid-template-columns: 1fr; gap: 7px; }
}

@media (max-width: 520px) {
  body { font-size: 14px; }
  .header-inner { padding: 26px 0 24px; }
  h1 { font-size: 26px; }
  .report-section { padding: 22px 16px; }
  .notice { padding: 13px 16px; }
  .metric-grid, .kv-grid { grid-template-columns: 1fr; }
  th, td { padding: 9px 10px; }
}

@media print {
  body { background: #fff; color: #000; }
  .nav-band { display: none; }
  .report-header { background: #fff; color: #000; border-bottom: 2px solid #000; }
  .eyebrow, .header-lead, .header-meta, .status-block span { color: #333; }
  .status-block { border-color: #777; background: #fff; }
  .report-main { width: 100%; margin: 0; border: 0; box-shadow: none; }
  .report-section { break-inside: avoid; }
  .table-wrap { overflow: visible; }
  a { color: #000; text-decoration: none; }
}
"""


def _text(value: Any, fallback: str = "Not available") -> str:
    if value is None or value == "":
        return escape(fallback)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return escape(str(value))


def _humanize(value: str) -> str:
    return value.replace("_", " ").strip().title()


def _number(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "Not evaluated"
    numeric = float(value)
    absolute = abs(numeric)
    if numeric != 0 and (absolute >= 10_000 or absolute < 0.001):
        return f"{numeric:.3e}"
    return f"{numeric:.{digits}f}".rstrip("0").rstrip(".")


def _joined(values: list[Any] | tuple[Any, ...] | None, fallback: str = "None") -> str:
    if not values:
        return escape(fallback)
    return escape(", ".join(str(value) for value in values))


def _safe_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return "#"
    return escape(value, quote=True)


def _tag(label: str, tone: str = "neutral") -> str:
    return f'<span class="tag tag-{tone}">{escape(label)}</span>'


def _score_tone(score: int) -> str:
    if score >= 4:
        return "good"
    if score == 3:
        return "info"
    if score >= 1:
        return "watch"
    return "danger"


def _status_tone(value: str) -> str:
    normalized = value.lower()
    if normalized in {
        "a",
        "b",
        "high",
        "passed",
        "unique",
        "direct",
        "supported",
        "include_candidate",
        "independent_association_replication",
    }:
        return "good"
    if normalized in {"c", "moderate", "indirect", "partial", "identity_confirmed", "literature_signal"}:
        return "info"
    if normalized in {
        "d",
        "low",
        "ambiguous",
        "background",
        "concern",
        "uncertain",
        "retrospective_association",
    }:
        return "watch"
    if normalized in {"e", "insufficient", "blocked", "unresolved", "conflicting", "exclude"}:
        return "danger"
    return "neutral"


def _metric(label: str, value: str, detail: str = "") -> str:
    detail_html = f'<span class="metric-detail">{escape(detail)}</span>' if detail else ""
    return (
        '<div class="metric">'
        f'<span class="metric-label">{escape(label)}</span>'
        f'<span class="metric-value">{value}</span>'
        f"{detail_html}</div>"
    )


def _display_timestamp(value: Any) -> str:
    if value is None:
        return "Not available"
    raw_value = str(value)
    try:
        parsed = datetime.fromisoformat(raw_value)
    except ValueError:
        return escape(raw_value)
    timezone_name = parsed.tzname()
    rendered = parsed.strftime("%Y-%m-%d %H:%M")
    if timezone_name:
        rendered = f"{rendered} {timezone_name}"
    return escape(rendered)


def _kv_grid(items: list[tuple[str, str]]) -> str:
    cells = "".join(f'<div class="kv-item"><dt>{escape(label)}</dt><dd>{value}</dd></div>' for label, value in items)
    return f'<dl class="kv-grid">{cells}</dl>'


def _table(headers: list[str], rows: list[list[str]], empty_message: str = "No records available.") -> str:
    if not rows:
        return f'<div class="empty-state">{escape(empty_message)}</div>'
    head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _list(items: list[str], empty_message: str, tone: str = "plain") -> str:
    if not items:
        return f'<div class="empty-state">{escape(empty_message)}</div>'
    rendered = "".join(f"<li>{escape(item)}</li>" for item in items)
    class_name = "plain-list" if tone == "plain" else f"message-list {tone}"
    return f'<ul class="{class_name}">{rendered}</ul>'


def _score_profile(scores: dict[str, EvidenceScore]) -> str:
    if not scores:
        return '<div class="empty-state">No evidence dimensions were scored.</div>'
    rows = []
    for score in scores.values():
        tone = _score_tone(score.score)
        width = score.score * 20
        rows.append(
            '<div class="score-row">'
            f'<div class="score-name">{escape(_humanize(score.dimension))}</div>'
            "<div>"
            f'<div class="score-track" role="meter" aria-label="{escape(_humanize(score.dimension))}" '
            f'aria-valuemin="0" aria-valuemax="5" aria-valuenow="{score.score}">'
            f'<div class="score-fill tone-{tone}" style="width:{width}%"></div></div>'
            f'<div class="score-value">{score.score} / 5</div>'
            "</div>"
            f'<div class="score-why">{escape(score.justification)}</div>'
            "</div>"
        )
    return '<div class="score-list">' + "".join(rows) + "</div>"


def _domain_profile(domains: dict[str, EvidenceDomainAssessment]) -> str:
    rows = [
        [
            _text(_humanize(assessment.dimension)),
            _tag(_humanize(assessment.status), _status_tone(assessment.status)),
            _text(assessment.justification),
        ]
        for assessment in domains.values()
    ]
    return _table(["Evidence domain", "Status", "Basis"], rows, "No evidence domains were assessed.")


def _conclusion_panel(supported_claim: str, unmet_requirements: list[str]) -> str:
    content = (
        '<div class="claim-panel"><strong>Supported claim</strong>'
        f"<p>{escape(supported_claim)}</p></div>"
        "<h3>What is still required</h3>"
    )
    return content + _list(unmet_requirements, "No unmet requirements were recorded.")


def _context_table(contexts: list[ContextOfUse]) -> str:
    rows = [
        [
            _tag(_humanize(context.category), "info"),
            _text(context.disease),
            _text(context.target_population),
            _text(context.clinical_setting),
            _text(context.specimen),
            _text(context.assay),
            _text(context.endpoint),
            _text(context.time_horizon),
            _text(context.reference_standard),
            _text(context.intervention),
            _text(context.baseline_comparator),
            _text(context.intended_action),
        ]
        for context in contexts
    ]
    return _table(
        [
            "Category",
            "Disease",
            "Population",
            "Setting",
            "Specimen",
            "Assay",
            "Endpoint",
            "Horizon",
            "Reference standard",
            "Intervention",
            "Baseline comparator",
            "Action",
        ],
        rows,
        "No context of use was supplied.",
    )


def _section(section_id: str, title: str, content: str, intro: str = "") -> str:
    intro_html = f'<p class="section-intro">{escape(intro)}</p>' if intro else ""
    return (
        f'<section class="report-section" id="{escape(section_id, quote=True)}">'
        f'<div class="section-heading"><h2>{escape(title)}</h2></div>{intro_html}{content}</section>'
    )


def _document(
    *,
    title: str,
    eyebrow: str,
    lead: str,
    status_label: str,
    status_value: str,
    header_meta: list[tuple[str, str]],
    nav: list[tuple[str, str]],
    sections: list[str],
) -> str:
    meta = "".join(f"<span><strong>{escape(label)}:</strong> {value}</span>" for label, value in header_meta)
    links = "".join(f'<a href="#{escape(target, quote=True)}">{escape(label)}</a>' for target, label in nav)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>{escape(title)}</title>
  <style>{REPORT_CSS}</style>
</head>
<body>
  <header class="report-header">
    <div class="header-inner">
      <p class="eyebrow">{escape(eyebrow)}</p>
      <div class="title-row">
        <div>
          <h1>{escape(title)}</h1>
          <p class="header-lead">{escape(lead)}</p>
        </div>
        <div class="status-block">
          <span>{escape(status_label)}</span>
          <strong>{escape(status_value)}</strong>
        </div>
      </div>
      <div class="header-meta">{meta}</div>
    </div>
  </header>
  <div class="nav-band"><nav class="report-nav" aria-label="Report sections">{links}</nav></div>
  <main class="report-main">
    <p class="notice"><strong>Research use only.</strong> This report summarizes retrieved evidence and completed analyses. It does not establish clinical validity or utility.</p>
    {"".join(sections)}
  </main>
  <footer class="report-footer">Generated by Biomarker Evidence Assessment Toolkit. Values shown here are taken from the machine-readable result object.</footer>
</body>
</html>
"""


def _provenance_items(provenance: dict[str, Any]) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for key, value in provenance.items():
        if isinstance(value, list):
            rendered = _joined(value)
        elif isinstance(value, dict):
            rendered = f'<span class="mono">{escape(json.dumps(value, sort_keys=True))}</span>'
        else:
            rendered = _text(value)
        items.append((_humanize(key), rendered))
    return items


def render_validation_html(result: ValidationResult) -> str:
    entity_name = result.entity.hgnc_symbol or result.entity.query
    generated_at = _display_timestamp(result.provenance.get("generated_at"))
    disease = _text(result.question.get("disease"))
    external_count = sum(dataset.get("role") == "external" for dataset in result.datasets)
    stage = result.evidence_conclusion.stage
    context_status = result.evidence_domains.get("context_of_use")

    overview = (
        '<div class="metric-grid">'
        + "".join(
            [
                _metric("Evidence stage", _tag(_humanize(stage), _status_tone(stage))),
                _metric(
                    "Entity resolution",
                    _tag(result.entity.resolution_confidence, _status_tone(result.entity.resolution_confidence)),
                    result.entity.mapping_source,
                ),
                _metric("Cohorts analysed", _text(len(result.datasets)), f"{external_count} external cohort(s)"),
                _metric(
                    "Context of use",
                    _tag(
                        _humanize(context_status.status) if context_status else "Not Evaluated",
                        _status_tone(context_status.status) if context_status else "neutral",
                    ),
                    f"{len(result.contexts_of_use)} claim context(s)",
                ),
            ]
        )
        + "</div>"
    )
    overview += _conclusion_panel(
        result.evidence_conclusion.supported_claim,
        result.evidence_conclusion.unmet_requirements,
    )
    overview += "<h3>Assessment question</h3>" + _kv_grid(
        [
            ("Disease", disease),
            ("Intended use", _joined(result.question.get("intended_uses"))),
            ("Molecular layer", _joined(result.question.get("molecular_layers"))),
            ("Specimen", _text(result.question.get("specimen"))),
            ("Endpoints", _joined(result.question.get("endpoints"))),
            ("Prespecified covariates", _joined(result.question.get("covariates"))),
        ]
    )

    qc_by_name = {qc.cohort_name: qc for qc in result.qc}
    cohort_rows: list[list[str]] = []
    qc_messages: list[str] = []
    for dataset in result.datasets:
        name = str(dataset.get("name", "Unnamed cohort"))
        qc = qc_by_name.get(name)
        status = _tag("not assessed", "neutral")
        if qc is not None:
            status = _tag("passed" if qc.passed else "blocked", "good" if qc.passed else "danger")
            qc_messages.extend(f"{name}: {failure}" for failure in qc.blocking_failures)
            qc_messages.extend(f"{name}: {warning}" for warning in qc.warnings)
        cohort_rows.append(
            [
                _text(name),
                _tag(str(dataset.get("role", "unknown")), "info" if dataset.get("role") == "external" else "neutral"),
                _text(dataset.get("disease")),
                _text(dataset.get("expression_layer")),
                f'<span class="number">{_text(qc.sample_count if qc else None)}</span>',
                f'<span class="number">{_text(qc.analyzable_sample_count if qc else None)}</span>',
                f'<span class="number">{_text(qc.tumor_count if qc else None)}</span>',
                f'<span class="number">{_text(qc.normal_count if qc else None)}</span>',
                f'<span class="number">{_text(qc.event_count if qc else None)}</span>',
                f'<span class="number">{_text(qc.missing_expression_count if qc else None)}</span>',
                status,
                (
                    "Not applicable"
                    if dataset.get("role") != "external"
                    else "independent: "
                    + _text(dataset.get("independent_from_discovery"))
                    + "; protocol locked: "
                    + _text(dataset.get("protocol_locked"))
                    + "; sample size: "
                    + ("documented" if dataset.get("sample_size_justification") else "not documented")
                ),
            ]
        )
    cohorts = _table(
        [
            "Cohort",
            "Role",
            "Disease",
            "Layer",
            "Samples",
            "Analyzable",
            "Tumor",
            "Normal",
            "Events",
            "Missing",
            "QC",
            "Replication gates",
        ],
        cohort_rows,
    )
    if qc_messages:
        cohorts += '<div class="callout"><strong>QC messages</strong>' + _list(qc_messages, "", "warning") + "</div>"

    diagnostic_rows = [
        [
            _text(item.cohort_name),
            f'<span class="number">{_number(item.tumor_mean)}</span><br><small>n={item.tumor_n}</small>',
            f'<span class="number">{_number(item.normal_mean)}</span><br><small>n={item.normal_n}</small>',
            f'<span class="number">{_number(item.mean_difference)}</span>',
            f'<span class="number">{_number(item.ci95[0])} to {_number(item.ci95[1])}</span>',
            f'<span class="number">{_number(item.auc)}</span>',
            _tag(_humanize(item.direction), "good" if item.direction != "no_difference" else "neutral"),
            f'<span class="number">{_number(item.p_value)}</span>',
        ]
        for item in result.analyses.diagnostic
    ]
    diagnostics = _table(
        ["Cohort", "Tumor mean", "Normal mean", "Mean difference", "95% CI", "AUC", "Direction", "P value"],
        diagnostic_rows,
        "No diagnostic analysis was completed. Check cohort QC and intended use.",
    )

    model_blocks: list[str] = []
    for model in result.analyses.prognostic:
        term_rows = [
            [
                _text(term.term),
                f'<span class="number">{_number(term.coefficient)}</span>',
                f'<span class="number">{_number(term.hazard_ratio)}</span>',
                f'<span class="number">{_number(term.ci95[0])} to {_number(term.ci95[1])}</span>',
                f'<span class="number">{_number(term.standard_error)}</span>',
            ]
            for term in model.terms
        ]
        warnings = _list(model.warnings, "No model warnings were recorded.", "warning")
        model_blocks.append(
            '<div class="model-block">'
            f"<h3>{escape(model.cohort_name)}</h3>"
            '<div class="subhead-meta">'
            f"<span>n={model.n}</span><span>events={model.event_count}</span>"
            f"<span>C-index={_number(model.concordance_index)}</span>"
            f"<span>log likelihood={_number(model.log_likelihood)}</span></div>"
            + _table(["Term", "Coefficient", "Hazard ratio", "95% CI", "Standard error"], term_rows)
            + "<h3>Model warnings</h3>"
            + warnings
            + "</div>"
        )
    prognostics = "".join(model_blocks) or '<div class="empty-state">No prognostic model was completed.</div>'

    utility_rows = [
        [
            _text(item.cohort_name),
            f'<span class="number">{_number(item.baseline_c_index)}</span>',
            f'<span class="number">{_number(item.augmented_c_index)}</span>',
            f'<span class="number">{_number(item.delta_c_index)}</span>',
            _text(item.interpretation),
        ]
        for item in result.clinical_utility.values()
    ]
    utility = _table(
        ["Cohort", "Baseline C-index", "Augmented C-index", "Delta", "Interpretation"],
        utility_rows,
        "Clinical utility was not evaluated.",
    )

    robustness_rows = [
        [
            _text(item.cohort_name),
            f'<span class="number">{item.bootstrap_iterations}</span>',
            f'<span class="number">{_text(item.random_seed)}</span>',
            f'<span class="number">{_number(item.diagnostic_direction_stability)}</span>',
            _joined(item.sensitivity_notes),
        ]
        for item in result.robustness.values()
    ]
    robustness = _table(
        ["Cohort", "Bootstrap iterations", "Random seed", "Direction stability", "Notes"],
        robustness_rows,
        "No robustness analysis was completed.",
    )

    entity = _kv_grid(
        [
            ("Submitted query", _text(result.entity.query)),
            ("HGNC symbol", _text(result.entity.hgnc_symbol)),
            ("Ensembl gene ID", _text(result.entity.ensembl_gene_id)),
            ("Entrez ID", _text(result.entity.entrez_id)),
            ("UniProt accession", _text(result.entity.uniprot_accession)),
            ("Aliases", _joined(result.entity.aliases)),
            ("Mapping source", _text(result.entity.mapping_source)),
            (
                "Resolution confidence",
                _tag(result.entity.resolution_confidence, _status_tone(result.entity.resolution_confidence)),
            ),
        ]
    )
    assumptions = result.question.get("assumptions", {})
    if isinstance(assumptions, dict):
        entity += "<h3>Analysis assumptions</h3>" + _kv_grid(
            [(_humanize(str(key)), _text(value)) for key, value in assumptions.items()]
        )

    dataset_rows = [
        [
            _text(dataset.get("name")),
            _text(dataset.get("source")),
            _text(dataset.get("version")),
            _text(dataset.get("access_date")),
            f'<span class="mono">{_text(dataset.get("expression_path"))}</span>',
            f'<span class="mono">{_text(dataset.get("metadata_path"))}</span>',
            _text(dataset.get("sample_size_justification")),
        ]
        for dataset in result.datasets
    ]
    provenance = _table(
        [
            "Dataset",
            "Source",
            "Version",
            "Access date",
            "Expression path",
            "Metadata path",
            "Sample-size justification",
        ],
        dataset_rows,
    )
    provenance += "<h3>Run provenance</h3>" + _kv_grid(_provenance_items(result.provenance))

    sections = [
        _section("overview", "Assessment at a glance", overview),
        _section(
            "evidence",
            "Evidence domains",
            _domain_profile(result.evidence_domains)
            + "<h3>Legacy heuristic indicators</h3>"
            + _score_profile(result.evidence_scores),
            "Domain status and the supported claim are the primary conclusion. Numeric indicators are retained for compatibility, are not a validated scale, and are not combined into a probability.",
        ),
        _section(
            "context",
            "Context of use",
            _context_table(result.contexts_of_use),
            "Each diagnostic, prognostic, or predictive claim should have one explicit population, setting, assay, endpoint, and intended action.",
        ),
        _section("cohorts", "Cohorts and quality control", cohorts),
        _section(
            "diagnostic",
            "Diagnostic expression evidence",
            diagnostics,
            "Continuous tumor-versus-normal comparisons; no expression cut-off was selected.",
        ),
        _section(
            "prognostic",
            "Prognostic association",
            prognostics,
            "Cox-model estimates are associative and should be read with their confidence intervals and warnings.",
        ),
        _section(
            "utility",
            "Apparent incremental discrimination",
            utility,
            "These same-cohort C-index differences are descriptive and do not establish clinical utility.",
        ),
        _section("robustness", "Robustness", robustness),
        _section("entity", "Entity and assumptions", entity),
        _section("limitations", "Limitations", _list(result.limitations, "No limitations were recorded.", "warning")),
        _section(
            "next-steps",
            "Recommended next validation",
            _list(result.recommended_next_validation, "No next steps were recorded."),
        ),
        _section("provenance", "Data and provenance", provenance),
    ]
    return _document(
        title=f"{entity_name} evidence assessment",
        eyebrow="Cohort evidence report",
        lead="Claim-bounded assessment of retrospective association, replication status, and evidence gaps.",
        status_label="Highest supported stage",
        status_value=_humanize(stage),
        header_meta=[
            ("Disease", disease),
            ("Specimen", _text(result.question.get("specimen"))),
            ("Generated", generated_at),
        ],
        nav=[
            ("overview", "Overview"),
            ("evidence", "Evidence"),
            ("context", "Context of use"),
            ("cohorts", "Cohorts & QC"),
            ("diagnostic", "Diagnostic"),
            ("prognostic", "Prognostic"),
            ("utility", "Apparent value"),
            ("robustness", "Robustness"),
            ("limitations", "Limitations"),
            ("provenance", "Provenance"),
        ],
        sections=sections,
    )


def _nested_identifier(value: Any) -> str:
    if value is None:
        return "Not available"
    if isinstance(value, dict):
        parts = []
        for key, nested in value.items():
            nested_text = ", ".join(str(item) for item in nested) if isinstance(nested, list) else str(nested)
            parts.append(f"{key}: {nested_text}")
        return "; ".join(parts)
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def render_external_html(result: ExternalEvidenceResult) -> str:
    entity_name = result.entity.hgnc_symbol or result.entity.query
    generated_at = _display_timestamp(result.provenance.get("generated_at"))
    stage = result.evidence_conclusion.stage
    context_status = result.evidence_domains.get("context_of_use")
    contexts = [result.context_of_use] if result.context_of_use is not None else []
    flow = result.literature_summary

    overview = (
        '<div class="metric-grid">'
        + "".join(
            [
                _metric(
                    "Evidence stage",
                    _tag(_humanize(stage), _status_tone(stage)),
                    "Highest claim supported by retrieved evidence",
                ),
                _metric(
                    "Entity resolution",
                    _tag(result.entity.resolution_confidence, _status_tone(result.entity.resolution_confidence)),
                    result.entity.mapping_source,
                ),
                _metric(
                    "Context of use",
                    _tag(
                        _humanize(context_status.status) if context_status else "Not Evaluated",
                        _status_tone(context_status.status) if context_status else "neutral",
                    ),
                    result.context_of_use.category if result.context_of_use else "not supplied",
                ),
                _metric("PubMed total hits", _text(flow.total_hits), "Before applying the retrieval cap"),
                _metric("Records retrieved", _text(flow.records_retrieved), f"{flow.pages_fetched} page(s)"),
                _metric("Automated-screen candidates", _text(flow.records_included), "Title/abstract rules only"),
                _metric(
                    "Biomarker effect-and-95%-CI candidates",
                    _text(flow.records_with_effect_estimates),
                    "Rule parsed from abstracts; unverified",
                ),
                _metric(
                    "Abstracts available", _text(flow.abstracts_available), "Processed transiently; not reproduced"
                ),
            ]
        )
        + "</div>"
    )
    overview += _conclusion_panel(
        result.evidence_conclusion.supported_claim,
        result.evidence_conclusion.unmet_requirements,
    )
    overview += "<h3>Assessment scope</h3>" + _kv_grid(
        [
            ("Biomarker query", _text(result.entity.query)),
            ("Resolved symbol", _text(result.entity.hgnc_symbol)),
            ("Disease", _text(result.disease)),
            ("Evidence mode", "Public identity plus automated PubMed title/abstract screening"),
        ]
    )

    flow_rows = [
        ["PubMed query hits", _text(flow.total_hits), "All records reported by ESearch before retrieval limits"],
        ["Retrieved", _text(flow.records_retrieved), "Unique records parsed from paginated EFetch responses"],
        ["Screened", _text(flow.records_screened), "Automated title/abstract rules applied"],
        ["Included candidates", _text(flow.records_included), "Biomarker, disease, and relevance terms present"],
        ["Excluded", _text(flow.records_excluded), "One or more required terms absent from title/abstract"],
        ["Uncertain", _text(flow.records_uncertain), "Insufficient metadata for an automated decision"],
        ["Abstracts available", _text(flow.abstracts_available), "Abstract text processed transiently"],
        [
            "Records with effect candidates",
            _text(flow.records_with_effect_estimates),
            "At least one same-sentence biomarker effect estimate paired with a 95% CI was rule parsed",
        ],
        ["Effect candidates extracted", _text(flow.effect_estimates_extracted), "Unverified candidate values"],
    ]
    flow_content = _table(["Flow step", "Count", "Definition"], flow_rows)
    if flow.truncated:
        cap = "all available up to 10,000" if flow.retrieval_cap is None else str(flow.retrieval_cap)
        flow_content += (
            '<div class="callout"><strong>Retrieval truncated.</strong> '
            f"The configured retrieval cap was {escape(cap)}; compare retrieved records with total hits.</div>"
        )
    if flow.retrieval_warnings:
        flow_content += (
            '<div class="callout"><strong>Retrieval warning(s)</strong>'
            + _list(
                flow.retrieval_warnings,
                "",
                "warning",
            )
            + "</div>"
        )

    entity = _kv_grid(
        [
            ("Submitted query", _text(result.entity.query)),
            ("Identifier type", _text(result.entity.id_type)),
            ("HGNC symbol", _text(result.entity.hgnc_symbol)),
            ("Ensembl gene ID", _text(result.entity.ensembl_gene_id)),
            ("Entrez ID", _text(result.entity.entrez_id)),
            ("UniProt accession", _text(result.entity.uniprot_accession)),
            ("Aliases", _joined(result.entity.aliases)),
            ("Mapping source", _text(result.entity.mapping_source)),
            (
                "Resolution confidence",
                _tag(result.entity.resolution_confidence, _status_tone(result.entity.resolution_confidence)),
            ),
        ]
    )
    if result.entity.candidates:
        entity += "<h3>Candidate mappings</h3>" + _table(
            ["Candidate"],
            [
                [f'<span class="mono">{escape(json.dumps(candidate, sort_keys=True))}</span>']
                for candidate in result.entity.candidates
            ],
        )

    database_rows = [
        [
            _text(record.get("source")),
            _text(record.get("symbol")),
            _text(record.get("name")),
            _text(record.get("entrezgene")),
            _text(_nested_identifier(record.get("ensembl"))),
            _text(_nested_identifier(record.get("uniprot"))),
            f'<span class="number">{_number(record.get("score")) if isinstance(record.get("score"), (int, float)) else _text(record.get("score"))}</span>',
        ]
        for record in result.database_records
    ]
    databases = _table(
        ["Source", "Symbol", "Name", "Entrez", "Ensembl", "UniProt", "Source score"],
        database_rows,
        "No external database records were retrieved.",
    )

    literature_items: list[str] = []
    for record in result.literature_records:
        matched = _joined(record.matched_terms, "No matched terms recorded")
        estimates = "; ".join(
            f"{_humanize(item.measure)} {_number(item.estimate)} "
            f"(95% CI {_number(item.ci95[0])} to {_number(item.ci95[1])})"
            for item in record.effect_estimates
        )
        literature_items.append(
            '<article class="literature-item">'
            f'<p class="literature-title"><a href="{_safe_url(record.url)}">{escape(record.title)}</a></p>'
            '<div class="literature-meta">'
            f'<span>PMID <span class="mono">{escape(record.pmid)}</span></span>'
            f"<span>{_text(record.journal)}</span><span>{_text(record.publication_date)}</span>"
            f"<span>{_tag(record.evidence_class, _status_tone(record.evidence_class))}</span>"
            f"<span>{_tag(_humanize(record.screening_decision), _status_tone(record.screening_decision))}</span>"
            f"<span>Abstract: {_text(record.abstract_available)}</span>"
            f"<span>Matched terms: {matched}</span>"
            f"<span>Screen basis: {_joined(record.screening_reasons, 'None recorded')}</span>"
            "</div>"
            + (
                f'<div class="callout"><strong>Unverified abstract effect candidate(s)</strong><br>{escape(estimates)}</div>'
                if estimates
                else ""
            )
            + "</article>"
        )
    literature_content = f'<div class="query-block"><strong>PubMed query</strong><br><span class="mono">{escape(result.literature_query or "No query recorded")}</span></div>'
    literature_content += (
        "".join(literature_items)
        if literature_items
        else '<div class="empty-state">No PubMed records were retrieved for this query.</div>'
    )

    provenance = _kv_grid(_provenance_items(result.provenance))
    sections = [
        _section("overview", "Assessment at a glance", overview),
        _section(
            "evidence",
            "Evidence domains",
            _domain_profile(result.evidence_domains)
            + "<h3>Legacy heuristic indicators</h3>"
            + _score_profile(result.evidence_scores),
            "Title/abstract retrieval and automated screening can support a literature signal only. Numeric indicators are retained for compatibility and do not represent evidence quality or success probability.",
        ),
        _section(
            "context",
            "Context of use",
            _context_table(contexts),
            "A biomarker claim is interpretable only for a specified population, setting, assay, endpoint, and intended action.",
        ),
        _section("entity", "Resolved entity", entity),
        _section("databases", "External database records", databases),
        _section(
            "literature-flow",
            "Literature flow",
            flow_content,
            "Counts distinguish PubMed hits, records actually retrieved, automated screening candidates, and records with rule-parsed same-sentence biomarker effect-and-95%-CI candidates. This is not full-text screening.",
        ),
        _section(
            "literature",
            "Disease-specific literature",
            literature_content,
            "Automated title/abstract decisions are retrieval aids only. Effect candidates must be checked against full text and tables; study eligibility and risk of bias are not appraised in this mode.",
        ),
        _section("limitations", "Limitations", _list(result.limitations, "No limitations were recorded.", "warning")),
        _section("provenance", "Provenance", provenance),
    ]
    return _document(
        title=f"{entity_name} external evidence assessment",
        eyebrow="Public evidence report",
        lead="Context-bounded identity and literature retrieval with explicit limits on supported claims.",
        status_label="Highest supported stage",
        status_value=_humanize(stage),
        header_meta=[
            ("Disease", _text(result.disease)),
            ("PubMed hits", _text(flow.total_hits)),
            ("Records retrieved", _text(flow.records_retrieved)),
            ("Generated", generated_at),
        ],
        nav=[
            ("overview", "Overview"),
            ("evidence", "Evidence"),
            ("context", "Context of use"),
            ("entity", "Entity"),
            ("databases", "Databases"),
            ("literature-flow", "Literature flow"),
            ("literature", "Literature"),
            ("limitations", "Limitations"),
            ("provenance", "Provenance"),
        ],
        sections=sections,
    )
