from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from biomarker_agent.version import __version__, runtime_versions

DatasetRole = Literal["discovery", "external"]
Layer = Literal["rna", "protein"]
BiomarkerCategory = Literal[
    "diagnostic",
    "prognostic",
    "predictive",
    "monitoring",
    "susceptibility_risk",
    "pharmacodynamic_response",
    "safety",
    "unspecified",
]
EvidenceDomainStatus = Literal["supported", "partial", "concern", "conflicting", "not_evaluated"]
EvidenceStageName = Literal[
    "not_assessed",
    "identity_confirmed",
    "literature_signal",
    "retrospective_association",
    "independent_association_replication",
    "locked_external_model_validation",
    "prospective_clinical_utility",
]


def _default_layers() -> list[Layer]:
    return ["rna"]


class CohortConfig(BaseModel):
    name: str
    role: DatasetRole
    expression_path: Path
    metadata_path: Path
    disease: str | None = None
    expression_layer: Layer = "rna"
    source: str = "user_supplied"
    version: str = "local"
    access_date: str | None = None
    independent_from_discovery: bool = False
    protocol_locked: bool = False
    sample_size_justification: str | None = None


class ContextOfUse(BaseModel):
    category: BiomarkerCategory
    disease: str
    target_population: str | None = None
    clinical_setting: str | None = None
    specimen: str | None = None
    assay: str | None = None
    endpoint: str | None = None
    time_horizon: str | None = None
    reference_standard: str | None = None
    intended_action: str | None = None
    intervention: str | None = None
    baseline_comparator: str | None = None

    @field_validator("disease")
    @classmethod
    def disease_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("context-of-use disease is required")
        return value.strip()


class DatasetConfig(BaseModel):
    discovery: CohortConfig
    external: list[CohortConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_separate_cohort_roles(self) -> Self:
        if self.discovery.role != "discovery":
            raise ValueError("datasets.discovery must have role='discovery'")
        if any(cohort.role != "external" for cohort in self.external):
            raise ValueError("every datasets.external entry must have role='external'")

        cohorts = [self.discovery, *self.external]
        names = [cohort.name for cohort in cohorts]
        if len(names) != len(set(names)):
            raise ValueError("cohort names must be unique")
        for cohort in self.external:
            if (
                cohort.expression_path == self.discovery.expression_path
                or cohort.metadata_path == self.discovery.metadata_path
            ):
                raise ValueError("discovery and external cohorts must not reuse the same input files")
        return self


class ValidationRequest(BaseModel):
    biomarker_id: str
    disease: str
    intended_uses: list[str] = Field(default_factory=lambda: ["diagnostic", "prognostic"])
    molecular_layers: list[Layer] = Field(default_factory=_default_layers)
    specimen: str = "tumor_tissue"
    endpoints: list[str] = Field(default_factory=lambda: ["overall_survival"])
    covariates: list[str] = Field(default_factory=list)
    analysis_mode: str = "full_validation"
    contexts_of_use: list[ContextOfUse] = Field(default_factory=list)
    datasets: DatasetConfig

    @field_validator("biomarker_id")
    @classmethod
    def biomarker_id_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("biomarker_id is required")
        return value.strip()

    @field_validator("disease")
    @classmethod
    def disease_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("disease is required; use an unambiguous full disease name when possible")
        return value.strip()

    @model_validator(mode="after")
    def contexts_match_request_disease(self) -> Self:
        expected = self.disease.strip().casefold()
        mismatched = [
            context.disease for context in self.contexts_of_use if context.disease.strip().casefold() != expected
        ]
        if mismatched:
            raise ValueError("every context-of-use disease must match the request disease")
        return self


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
    random_seed: int | None = None
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


class EvidenceDomainAssessment(BaseModel):
    dimension: str
    status: EvidenceDomainStatus
    justification: str


class EvidenceConclusion(BaseModel):
    stage: EvidenceStageName = "not_assessed"
    supported_claim: str = "No evidence claim has been assessed."
    unmet_requirements: list[str] = Field(default_factory=list)


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
    context_of_use: ContextOfUse | None = None
    evidence_domains: dict[str, EvidenceDomainAssessment] = Field(default_factory=dict)
    evidence_conclusion: EvidenceConclusion = Field(default_factory=EvidenceConclusion)
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
    contexts_of_use: list[ContextOfUse] = Field(default_factory=list)
    evidence_domains: dict[str, EvidenceDomainAssessment] = Field(default_factory=dict)
    evidence_conclusion: EvidenceConclusion = Field(default_factory=EvidenceConclusion)
    evidence_scores: dict[str, EvidenceScore]
    overall_grade: Literal["A", "B", "C", "D", "E"]
    limitations: list[str]
    recommended_next_validation: list[str]
    provenance: dict[str, Any]

    @classmethod
    def now_provenance(cls) -> dict[str, Any]:
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "software": "biomarker-evidence-assessment",
            "software_version": __version__,
            "phase": "phase_2_claim_bounded_assessment",
            "runtime_versions": runtime_versions(),
        }
