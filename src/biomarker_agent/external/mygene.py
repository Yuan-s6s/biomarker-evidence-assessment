from __future__ import annotations

from typing import Any

from biomarker_agent.external.http import get_json
from biomarker_agent.schemas import BiomarkerEntity


MYGENE_QUERY_URL = "https://mygene.info/v3/query"


def _first(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value)


def _uniprot(hit: dict[str, Any]) -> str | None:
    uniprot = hit.get("uniprot")
    if isinstance(uniprot, dict):
        return _first(uniprot.get("Swiss-Prot") or uniprot.get("TrEMBL"))
    return None


def query_mygene(query: str, size: int = 5) -> tuple[BiomarkerEntity, list[dict[str, Any]]]:
    fields = "symbol,name,entrezgene,ensembl.gene,uniprot,alias,taxid"
    payload = get_json(MYGENE_QUERY_URL, {"q": query, "species": "human", "fields": fields, "size": size})
    hits = [hit for hit in payload.get("hits", []) if hit.get("taxid") == 9606]
    records = [
        {
            "source": "MyGene.info",
            "symbol": hit.get("symbol"),
            "name": hit.get("name"),
            "entrezgene": hit.get("entrezgene"),
            "ensembl": hit.get("ensembl"),
            "uniprot": hit.get("uniprot"),
            "score": hit.get("_score"),
        }
        for hit in hits
    ]
    if not hits:
        return BiomarkerEntity(query=query, id_type="external_query", resolution_confidence="unresolved", mapping_source="mygene_v3"), records

    top = hits[0]
    ensembl = top.get("ensembl")
    if isinstance(ensembl, list):
        ensembl_gene_id = _first([item.get("gene") for item in ensembl if isinstance(item, dict) and item.get("gene")])
    elif isinstance(ensembl, dict):
        ensembl_gene_id = _first(ensembl.get("gene"))
    else:
        ensembl_gene_id = None

    candidates = [{k: str(v) for k, v in record.items() if v is not None and k in {"symbol", "entrezgene"}} for record in records[:size]]
    confidence = "unique" if len(hits) == 1 or str(top.get("symbol", "")).upper() == query.upper() else "ambiguous"
    return (
        BiomarkerEntity(
            query=query,
            id_type="external_query",
            hgnc_symbol=top.get("symbol"),
            ensembl_gene_id=ensembl_gene_id,
            entrez_id=str(top.get("entrezgene")) if top.get("entrezgene") else None,
            uniprot_accession=_uniprot(top),
            aliases=[str(alias) for alias in top.get("alias", [])] if isinstance(top.get("alias"), list) else [],
            mapping_source="mygene_v3",
            resolution_confidence=confidence,
            candidates=[] if confidence == "unique" else candidates,
        ),
        records,
    )
