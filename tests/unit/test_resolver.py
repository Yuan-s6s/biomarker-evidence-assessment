import pytest

from biomarker_agent.resolver import AmbiguousIdentifierError, OfflineResolver, UnresolvedIdentifierError


def test_resolves_symbol_ensembl_entrez_and_uniprot():
    resolver = OfflineResolver()
    assert resolver.resolve("RAB38").hgnc_symbol == "RAB38"
    assert resolver.resolve("ENSG00000123892").hgnc_symbol == "RAB38"
    assert resolver.resolve("23682").hgnc_symbol == "RAB38"
    assert resolver.resolve("P57729").hgnc_symbol == "RAB38"


def test_ambiguous_identifier_blocks():
    with pytest.raises(AmbiguousIdentifierError) as exc:
        OfflineResolver().resolve("RAB")
    assert exc.value.entity.resolution_confidence == "ambiguous"
    assert len(exc.value.entity.candidates) == 2


def test_unresolved_identifier_blocks():
    with pytest.raises(UnresolvedIdentifierError):
        OfflineResolver().resolve("NOT_A_REAL_GENE")
