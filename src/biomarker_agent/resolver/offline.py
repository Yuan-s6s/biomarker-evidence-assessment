from __future__ import annotations

import re
from typing import TypedDict

from biomarker_agent.schemas import BiomarkerEntity


class AmbiguousIdentifierError(ValueError):
    def __init__(self, entity: BiomarkerEntity):
        self.entity = entity
        super().__init__("Identifier resolved to multiple candidate entities")


class UnresolvedIdentifierError(ValueError):
    def __init__(self, entity: BiomarkerEntity):
        self.entity = entity
        super().__init__("Identifier could not be resolved")


class MockEntity(TypedDict):
    hgnc_symbol: str
    ensembl_gene_id: str
    entrez_id: str
    uniprot_accession: str
    aliases: list[str]


MOCK_ENTITIES: list[MockEntity] = [
    {
        "hgnc_symbol": "RAB38",
        "ensembl_gene_id": "ENSG00000123892",
        "entrez_id": "23682",
        "uniprot_accession": "P57729",
        "aliases": ["NY-MEL-1", "rrp29"],
    },
    {
        "hgnc_symbol": "ZNF185",
        "ensembl_gene_id": "ENSG00000147394",
        "entrez_id": "7739",
        "uniprot_accession": "O15231",
        "aliases": ["LIMR"],
    },
    {
        "hgnc_symbol": "TP53",
        "ensembl_gene_id": "ENSG00000141510",
        "entrez_id": "7157",
        "uniprot_accession": "P04637",
        "aliases": ["P53", "BCC7"],
    },
]


class OfflineResolver:
    """Deterministic mock resolver for Phase 1 local workflows."""

    def detect_id_type(self, query: str) -> str:
        value = query.strip()
        if re.fullmatch(r"ENSG\d+(?:\.\d+)?", value, re.IGNORECASE):
            return "ensembl_gene_id"
        if re.fullmatch(r"\d+", value):
            return "entrez_id"
        if re.fullmatch(r"[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9][A-Z][A-Z0-9]{2}[0-9]", value):
            return "uniprot_accession"
        return "gene_symbol_or_alias"

    def resolve(self, query: str) -> BiomarkerEntity:
        id_type = self.detect_id_type(query)
        normalized = query.strip().upper().split(".")[0]
        matches = []
        for candidate in MOCK_ENTITIES:
            haystack = {
                candidate["hgnc_symbol"].upper(),
                candidate["ensembl_gene_id"].upper(),
                candidate["entrez_id"],
                candidate["uniprot_accession"].upper(),
                *(alias.upper() for alias in candidate["aliases"]),
            }
            if normalized in haystack:
                matches.append(candidate)
        if normalized == "RAB":
            matches = [
                MOCK_ENTITIES[0],
                {
                    "hgnc_symbol": "RAB37",
                    "ensembl_gene_id": "ENSG00000172794",
                    "entrez_id": "326624",
                    "uniprot_accession": "Q96AX2",
                    "aliases": [],
                },
            ]

        if len(matches) == 1:
            return BiomarkerEntity(
                query=query,
                id_type=id_type,
                resolution_confidence="unique",
                **matches[0],
            )
        if len(matches) > 1:
            resolved = BiomarkerEntity(
                query=query,
                id_type=id_type,
                resolution_confidence="ambiguous",
                candidates=[{k: str(v) for k, v in match.items() if k != "aliases"} for match in matches],
            )
            raise AmbiguousIdentifierError(resolved)
        unresolved = BiomarkerEntity(query=query, id_type=id_type, resolution_confidence="unresolved")
        raise UnresolvedIdentifierError(unresolved)
