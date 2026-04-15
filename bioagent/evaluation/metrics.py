"""Quantitative evaluation metrics for BioAgent research output.

Metrics are organized in six dimensions that mirror what a journal reviewer
would assess when evaluating an AI-generated research paper.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any

from bioagent.state.schema import ResearchState

logger = logging.getLogger(__name__)


@dataclass
class LiteratureMetrics:
    """Metrics for the literature review phase."""

    papers_found: int = 0
    gaps_identified: int = 0
    # Precision / recall against a gold-standard set (if provided)
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    # Quality proxy: fraction of papers with non-empty titles
    title_coverage: float = 0.0

    @property
    def score(self) -> float:
        """Composite score 0–10."""
        base = min(self.papers_found / 10.0, 1.0) * 4  # up to 4 pts for paper count
        base += min(self.gaps_identified / 5.0, 1.0) * 3  # up to 3 pts for gaps
        base += self.title_coverage * 3  # up to 3 pts for metadata quality
        return round(base, 2)


@dataclass
class HypothesisMetrics:
    """Metrics for hypothesis generation quality."""

    hypotheses_generated: int = 0
    hypothesis_selected: bool = False
    has_novelty_score: bool = False
    has_testability_score: bool = False
    has_rationale: bool = False

    @property
    def score(self) -> float:
        points = 0.0
        points += min(self.hypotheses_generated / 3.0, 1.0) * 3
        points += 2 if self.hypothesis_selected else 0
        points += 2 if self.has_novelty_score else 0
        points += 2 if self.has_testability_score else 0
        points += 1 if self.has_rationale else 0
        return round(points, 2)


@dataclass
class AnalysisMetrics:
    """Metrics for code execution and analysis quality."""

    code_artifacts: int = 0
    execution_results: int = 0
    execution_success_rate: float = 0.0
    figures_generated: int = 0
    validation_passed: bool | None = None

    @property
    def score(self) -> float:
        points = min(self.code_artifacts / 3.0, 1.0) * 2
        points += self.execution_success_rate * 4
        points += min(self.figures_generated / 3.0, 1.0) * 2
        points += 2 if self.validation_passed else (1 if self.validation_passed is None else 0)
        return round(points, 2)


@dataclass
class WritingMetrics:
    """Metrics for the paper writing phase."""

    sections_written: list[str] = field(default_factory=list)
    total_word_count: int = 0
    has_abstract: bool = False
    has_methods: bool = False
    has_results: bool = False
    has_discussion: bool = False
    # Flesch-Kincaid readability (higher = more readable)
    avg_readability: float | None = None

    @property
    def completeness(self) -> float:
        required = ["abstract", "introduction", "methods", "results", "discussion"]
        written = set(s.lower() for s in self.sections_written)
        return sum(1 for r in required if r in written) / len(required)

    @property
    def score(self) -> float:
        points = self.completeness * 5
        # Word count proxy: 500–3000 words is a reasonable range
        wc = self.total_word_count
        if wc >= 500:
            points += min((wc - 500) / 2500.0, 1.0) * 3
        points += 2 if (self.avg_readability is not None and self.avg_readability > 30) else 0
        return round(points, 2)


@dataclass
class FigureMetrics:
    """Metrics for generated figures."""

    figure_count: int = 0
    figures_with_captions: int = 0
    figures_with_paths: int = 0

    @property
    def caption_coverage(self) -> float:
        if not self.figure_count:
            return 0.0
        return self.figures_with_captions / self.figure_count

    @property
    def score(self) -> float:
        points = min(self.figure_count / 4.0, 1.0) * 5
        points += self.caption_coverage * 3
        points += (self.figures_with_paths / max(self.figure_count, 1)) * 2
        return round(points, 2)


@dataclass
class EfficiencyMetrics:
    """End-to-end efficiency metrics."""

    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    phases_completed: list[str] = field(default_factory=list)
    review_score: int | None = None
    review_recommendation: str = ""

    @property
    def score(self) -> float:
        """Score 0–10 based on review outcome and pipeline completion."""
        base = 0.0
        if self.review_score is not None:
            base += self.review_score  # 1–10 from self-review
        else:
            # Use pipeline completion as proxy
            expected = 8  # approximate number of unique phases
            base += min(len(set(self.phases_completed)) / expected, 1.0) * 7
        return round(min(base, 10.0), 2)


@dataclass
class EvaluationReport:
    """Aggregated evaluation report across all six dimensions."""

    research_topic: str = ""
    literature: LiteratureMetrics = field(default_factory=LiteratureMetrics)
    hypothesis: HypothesisMetrics = field(default_factory=HypothesisMetrics)
    analysis: AnalysisMetrics = field(default_factory=AnalysisMetrics)
    writing: WritingMetrics = field(default_factory=WritingMetrics)
    figures: FigureMetrics = field(default_factory=FigureMetrics)
    efficiency: EfficiencyMetrics = field(default_factory=EfficiencyMetrics)

    # Optional: recall/precision against a benchmark case
    benchmark_precision: float | None = None
    benchmark_recall: float | None = None
    benchmark_case: str = ""

    @property
    def weighted_score(self) -> float:
        """Weighted composite score (0–10) mirroring Bioinformatics review criteria.

        Weights inspired by journal review rubrics:
          - Scientific rigor (analysis): 30%
          - Writing quality: 25%
          - Novelty (hypothesis): 20%
          - Figures: 15%
          - Literature coverage: 10%
        """
        return round(
            self.analysis.score * 0.30
            + self.writing.score * 0.25
            + self.hypothesis.score * 0.20
            + self.figures.score * 0.15
            + self.literature.score * 0.10,
            2,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "research_topic": self.research_topic,
            "weighted_score": self.weighted_score,
            "literature": {
                "papers_found": self.literature.papers_found,
                "gaps_identified": self.literature.gaps_identified,
                "score": self.literature.score,
                "precision": self.literature.precision,
                "recall": self.literature.recall,
            },
            "hypothesis": {
                "generated": self.hypothesis.hypotheses_generated,
                "selected": self.hypothesis.hypothesis_selected,
                "score": self.hypothesis.score,
            },
            "analysis": {
                "code_artifacts": self.analysis.code_artifacts,
                "execution_success_rate": self.analysis.execution_success_rate,
                "figures_generated": self.analysis.figures_generated,
                "validation_passed": self.analysis.validation_passed,
                "score": self.analysis.score,
            },
            "writing": {
                "sections": self.writing.sections_written,
                "word_count": self.writing.total_word_count,
                "completeness": self.writing.completeness,
                "score": self.writing.score,
            },
            "figures": {
                "count": self.figures.figure_count,
                "caption_coverage": self.figures.caption_coverage,
                "score": self.figures.score,
            },
            "efficiency": {
                "total_tokens": self.efficiency.total_tokens,
                "estimated_cost_usd": self.efficiency.estimated_cost_usd,
                "review_score": self.efficiency.review_score,
                "review_recommendation": self.efficiency.review_recommendation,
                "score": self.efficiency.score,
            },
            "benchmark": {
                "case": self.benchmark_case,
                "precision": self.benchmark_precision,
                "recall": self.benchmark_recall,
            },
        }

    def summary(self) -> str:
        lines = [
            f"EvaluationReport: {self.research_topic}",
            f"  Weighted score: {self.weighted_score:.1f}/10",
            f"  Literature:  {self.literature.score:.1f}/10  "
            f"({self.literature.papers_found} papers, {self.literature.gaps_identified} gaps)",
            f"  Hypothesis:  {self.hypothesis.score:.1f}/10  "
            f"({self.hypothesis.hypotheses_generated} generated)",
            f"  Analysis:    {self.analysis.score:.1f}/10  "
            f"(success rate: {self.analysis.execution_success_rate:.0%})",
            f"  Writing:     {self.writing.score:.1f}/10  "
            f"(completeness: {self.writing.completeness:.0%}, {self.writing.total_word_count} words)",
            f"  Figures:     {self.figures.score:.1f}/10  "
            f"({self.figures.figure_count} figures)",
            f"  Review:      {self.efficiency.review_score or 'N/A'}/10  "
            f"({self.efficiency.review_recommendation})",
        ]
        return "\n".join(lines)


# ── Readability helpers ─────────────────────────────────────────────────────

def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _syllable_count(word: str) -> int:
    """Crude syllable counter for Flesch readability."""
    word = word.lower().rstrip("esz")
    vowels = "aeiouy"
    count = 0
    prev_vowel = False
    for ch in word:
        is_v = ch in vowels
        if is_v and not prev_vowel:
            count += 1
        prev_vowel = is_v
    return max(count, 1)


def _flesch_reading_ease(text: str) -> float:
    """Compute Flesch Reading Ease score (higher = more readable)."""
    sentences = max(len(re.split(r"[.!?]+", text)), 1)
    words = re.findall(r"\b\w+\b", text)
    if not words:
        return 0.0
    syllables = sum(_syllable_count(w) for w in words)
    return 206.835 - 1.015 * (len(words) / sentences) - 84.6 * (syllables / len(words))


# ── Main evaluate function ──────────────────────────────────────────────────

def evaluate_run(
    state: ResearchState,
    gold_standard_pmids: list[str] | None = None,
    benchmark_case: str = "",
) -> EvaluationReport:
    """Compute an EvaluationReport from a completed ResearchState.

    Parameters
    ----------
    state : ResearchState
        The final state after the research graph completes.
    gold_standard_pmids : list[str], optional
        Known relevant PMIDs for precision/recall computation.
    benchmark_case : str, optional
        Name of the benchmark case (e.g. "braf_melanoma").

    Returns
    -------
    EvaluationReport
    """
    report = EvaluationReport(research_topic=state.get("research_topic", ""))
    report.benchmark_case = benchmark_case

    # ── Literature ──────────────────────────────────────────────────────────
    papers = state.get("papers", [])
    gaps = state.get("research_gaps", [])
    report.literature.papers_found = len(papers)
    report.literature.gaps_identified = len(gaps)
    if papers:
        with_title = sum(1 for p in papers if isinstance(p, dict) and p.get("title"))
        report.literature.title_coverage = with_title / len(papers)

    if gold_standard_pmids:
        found_ids = {str(p.get("id", "")) for p in papers if isinstance(p, dict)}
        gold = set(gold_standard_pmids)
        tp = len(found_ids & gold)
        precision = tp / len(found_ids) if found_ids else 0.0
        recall = tp / len(gold) if gold else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        report.literature.precision = round(precision, 3)
        report.literature.recall = round(recall, 3)
        report.literature.f1 = round(f1, 3)
        report.benchmark_precision = report.literature.precision
        report.benchmark_recall = report.literature.recall

    # ── Hypothesis ──────────────────────────────────────────────────────────
    hypotheses = state.get("hypotheses", [])
    selected = state.get("selected_hypothesis")
    report.hypothesis.hypotheses_generated = len(hypotheses)
    report.hypothesis.hypothesis_selected = bool(selected)
    if hypotheses and isinstance(hypotheses[0], dict):
        sample = hypotheses[0]
        report.hypothesis.has_novelty_score = "novelty_score" in sample
        report.hypothesis.has_testability_score = "testability_score" in sample
        report.hypothesis.has_rationale = bool(sample.get("rationale") or sample.get("reasoning"))

    # ── Analysis ────────────────────────────────────────────────────────────
    code_artifacts = state.get("code_artifacts", [])
    execution_results = state.get("execution_results", [])
    figures = state.get("figures", [])
    validation = state.get("validation_status")

    report.analysis.code_artifacts = len(code_artifacts)
    report.analysis.execution_results = len(execution_results)
    report.analysis.figures_generated = len(figures)
    report.analysis.validation_passed = validation.get("passed") if isinstance(validation, dict) else None

    if execution_results:
        successes = sum(
            1 for r in execution_results
            if isinstance(r, dict) and r.get("exit_code", 1) == 0
        )
        report.analysis.execution_success_rate = successes / len(execution_results)

    # ── Writing ─────────────────────────────────────────────────────────────
    paper_sections = state.get("paper_sections", {})
    report.writing.sections_written = list(paper_sections.keys())
    report.writing.has_abstract = "abstract" in paper_sections
    report.writing.has_methods = "methods" in paper_sections
    report.writing.has_results = "results" in paper_sections
    report.writing.has_discussion = "discussion" in paper_sections

    all_text = ""
    for sec in paper_sections.values():
        if isinstance(sec, dict):
            all_text += sec.get("content", "") + " "
        elif isinstance(sec, str):
            all_text += sec + " "

    report.writing.total_word_count = _word_count(all_text)
    if all_text.strip():
        try:
            report.writing.avg_readability = _flesch_reading_ease(all_text)
        except Exception:
            pass

    # ── Figures ─────────────────────────────────────────────────────────────
    report.figures.figure_count = len(figures)
    report.figures.figures_with_captions = sum(
        1 for f in figures if isinstance(f, dict) and f.get("caption")
    )
    report.figures.figures_with_paths = sum(
        1 for f in figures if isinstance(f, dict) and f.get("path")
    )

    # ── Efficiency / Review ─────────────────────────────────────────────────
    phase_history = state.get("phase_history", [])
    report.efficiency.phases_completed = list(phase_history)

    review_feedback = state.get("review_feedback", [])
    if review_feedback:
        latest = review_feedback[-1] if isinstance(review_feedback, list) else review_feedback
        if isinstance(latest, dict):
            report.efficiency.review_score = latest.get("score")
            report.efficiency.review_recommendation = latest.get("recommendation", "")

    # Token usage (from global tracker)
    try:
        from bioagent.llm.token_tracking import global_token_usage

        report.efficiency.total_tokens = global_token_usage.total
        report.efficiency.estimated_cost_usd = global_token_usage.estimated_cost_usd
    except Exception:
        pass

    return report
