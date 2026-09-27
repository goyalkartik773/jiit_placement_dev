"""Classification layer: spec taxonomy mapping + optional LLM fallback."""

from app.classifiers.taxonomy import TAXONOMY, TaxonomyResult, classify_taxonomy

__all__ = ["TAXONOMY", "TaxonomyResult", "classify_taxonomy"]
