"""Evaluation framework for assessing BioAgent research output quality.

Provides quantitative metrics across six dimensions:
  - Literature coverage
  - Hypothesis quality
  - Analysis correctness
  - Writing quality
  - Figure quality
  - End-to-end efficiency
"""

from bioagent.evaluation.metrics import EvaluationReport, evaluate_run
from bioagent.evaluation.provenance import ProvenanceTracker, record_provenance

__all__ = ["EvaluationReport", "evaluate_run", "ProvenanceTracker", "record_provenance"]
