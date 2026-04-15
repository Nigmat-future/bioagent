"""Individual benchmark cases with ground-truth annotations."""

from benchmarks.cases.braf_melanoma import BRAF_MELANOMA
from benchmarks.cases.tp53_pancancer import TP53_PANCANCER
from benchmarks.cases.scrna_pbmc import SCRNA_PBMC

ALL_CASES = [BRAF_MELANOMA, TP53_PANCANCER, SCRNA_PBMC]

__all__ = ["BRAF_MELANOMA", "TP53_PANCANCER", "SCRNA_PBMC", "ALL_CASES"]
