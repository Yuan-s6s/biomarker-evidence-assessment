from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


DatasetRole = Literal["discovery", "external"]
Layer = Literal["rna", "protein"]


class CohortConfig(BaseModel):
    name: str
    role: DatasetRole
    expression_path: Path
    metadata_path: Path
    expression_layer: Layer = "rna"
    source: str = "user_supplied"
    version: str = "local"
    access_date: str | None = None


class DatasetConfig(BaseModel):
    discovery: CohortConfig
    external: list[CohortConfig] = Field(default_factory=list)


class ValidationRequest(BaseModel):
    biomarker_id: str
    disease: str = "LSCC"
    intended_uses: list[str] = Field(default_factory=lambda: ["diagnostic", "prognostic"])
    molecular_layers: list[Layer] = Field(default_factory=lambda: ["rna"])
    specimen: str = "tumor_tissue"
    endpoints: list[str] = Field(default_factory=lambda: ["overall_survival"])
    covariates: list[str] = Field(default_factory=list)
    analysis_mode: str = "full_validation"
    datasets: DatasetConfig

    @field_validator("biomarker_id")
    @classmethod
    def biomarker_id_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("biomarker_id is required")
        return value.strip()


class BiomarkerEntity(BaseModel):
    query: str
    id_type: str
    hgnc_symbol: str | None = None
    ensembl_gene_id: str | None = None
    entrez_id: str | None = None
    uniprot_accession: str | None = None
    aliases: list[str] = Field(default_factory=list)
    mapping_source: str = "offline_mock_v1"
    resolution_confidence: Literal["unique", "ambiguous", "unresolved"]
    candidates: list[dict[str, str]] = Field(default_factory=list)


class QCResult(BaseModel):
    cohort_name: str
    passed: bool
    blocking_failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    sample_count: int
    analyzable_sample_count: int
    tumor_count: int = 0
    normal_count: int = 0
    event_count: int = 0
    missing_expression_count: int = 0


class DiagnosticResult(BaseModel):
    cohort_name: str
    biomarker: str
    tumor_n: int
    normal_n: int
    tumor_mean: float
    normal_mean: float
    mean_difference: float
    ci95: tuple[float, float]
    test_statistic: float
    p_value: float
    auc: float
    direction: Literal["higher_in_tumor", "lower_in_tumor", "no_difference"]


class CoxTerm(BaseModel):
    term: str
    coefficient: float
    hazard_ratio: float
    standard_error: float
    ci95: tuple[float, float]


class PrognosticResult(BaseModel):
    cohort_name: str
    biomarker: str
    n: int
    event_count: int
    terms: list[CoxTerm]
    log_likelihood: float
    concordance_index: float
    warnings: list[str] = Field(default_factory=list)


class ClinicalUtilityResult(BaseModel):
    cohort_name: str
    baseline_c_index: float | None
    augmented_c_index: float | None
    delta_c_index: float | None
    interpretation: str


class RobustnessResult(BaseModel):
    cohort_name: str
    bootstrap_iterations: int
    diagnostic_direction_stability: float | None
    sensitivity_notes: list[str] = Field(default_factory=list)


class AnalysisBundle(BaseModel):
    diagnostic: list[DiagnosticResult] = Field(default_factory=list)
    prognostic: list[PrognosticResult] = Field(default_factory=list)
    rna_protein: list[dict[str, Any]] = Field(default_factory=list)


class EvidenceScore(BaseModel):
    dimension: str
    score: int = Field(ge=0, le=5)
    justification: str


class LiteratureRecord(BaseModel):
    pmid: str
    title: str
    journal: str | None = None
    publication_date: str | None = None
    url: str
    evidence_class: Literal["direct", "indirect", "background"]
    matched_terms: list[str] = Field(default_factory=list)


class ExternalEvidenceResult(BaseModel):
    entity: BiomarkerEntity
    disease: str
    literature_query: str
    literature_records: list[LiteratureRecord] = Field(default_factory=list)
    database_records: list[dict[str, Any]] = Field(default_factory=list)
    evidence_scores: dict[str, EvidenceScore]
    overall_confidence: Literal["high", "moderate", "low", "insufficient"]
    limitations: list[str]
    provenance: dict[str, Any]


class ValidationResult(BaseModel):
    entity: BiomarkerEntity
    question: dict[str, Any]
    datasets: list[dict[str, Any]]
    qc: list[QCResult]
    analyses: AnalysisBundle
    robustness: dict[str, RobustnessResult]
    clinical_utility: dict[str, ClinicalUtilityResult]
    evidence_scores: dict[str, EvidenceScore]
    overall_grade: Literal["A", "B", "C", "D", "E"]
    limitations: list[str]
    recommended_next_validation: list[str]
    provenance: dict[str, Any]

    @classmethod
    def now_provenance(cls) -> dict[str, Any]:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "software": "biomarker-validation-agent",
            "phase": "phase_1_local_mvp",
        }
