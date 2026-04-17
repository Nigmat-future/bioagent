# Supplementary Material S4 — Error Analysis

This supplement extends the error analysis subsection of the main text with concrete log excerpts, incidence rates, and mitigations.

## S4.1 Observed Failure Modes

### F1. Literature retrieval brittleness

**Symptom.** Canonical clinical-trial papers (e.g.\ Chapman 2011, Larkin 2015) are not returned by BioMCP when the research question is phrased in mechanistic terms (e.g.\ "BRAF V600E resistance mechanisms").

**Example (BRAF run, phase `literature_review`).** Query `"BRAF V600E melanoma drug resistance"` returned 2 preprints and 0 of the 7 gold-standard PMIDs. Only when a second retrieval pass used explicit PMID queries did the trial papers appear.

**Incidence.** Observed in 3/7 development runs where the question was phrased mechanistically. Not observed for drug-centric phrasings ("vemurafenib response rate").

**Mitigation.** `bioagent/prompts/literature.md` instructs the LiteratureAgent to issue BOTH mechanistic and drug-centric queries. A planned enhancement is to add a post-hoc validation pass that checks retrieved PMIDs against gold-standard lists for well-studied diseases.

### F2. Parser fragility for unstructured LLM output

**Symptom.** The WriterAgent occasionally emits the Methods section without a leading `## METHODS` header, or closes the `## REFERENCES` section with triple backticks instead of an explicit fence.

**Incidence.** ~8% of writing invocations (3 out of 38 observed runs).

**Log excerpt.**

```
WARNING: [writer] section extractor failed for 'references' — falling back to regex
INFO: [writer] recovered references section via \d{8} pattern match
```

**Mitigation.** Multi-layer fallback parsing in `bioagent/agents/writer.py`: first try fenced headers, then regex-match known section names, then fall back to PMID pattern matching. No observed run has failed to extract all five IMRAD sections after fallback.

### F3. Transient tool errors

**Symptom.** NCBI E-utilities and cBioPortal REST endpoints return HTTP 503 under load.

**Log excerpt.**

```
WARNING: [cbioportal_tools] attempt 1 failed (503), retrying in 2s
WARNING: [cbioportal_tools] attempt 2 failed (503), retrying in 4s
INFO: [cbioportal_tools] attempt 3 succeeded
```

**Incidence.** ~15% of data-acquisition phases across development runs.

**Mitigation.** `tenacity`-backed exponential backoff with 3 retries. All observed transients resolve within 3 attempts.

### F4. Cost-vs-quality frontier

**Symptom.** At the default budget cap (`BIOAGENT_COST_BUDGET_USD=5`), the maximum-of-two review revision cycles may complete without the manuscript crossing the default review score threshold (7/10).

**Example (BRAF run).** Final review score 5/10. The run proceeded to export because `BIOAGENT_MIN_REVIEW_SCORE` was set to 5 for this benchmark configuration; at the default threshold the manuscript would have been returned for a third revision that was forbidden by `max_review_rounds=2`.

**Mitigation options** (all exposed as settings):

- Raise `max_review_rounds` from 2 to 3 or 4 (linear cost increase).
- Raise `cost_budget_usd` from 5 to 10 (removes the hard stop).
- Lower `min_review_score` from 7 to 5 (accepts lower-quality output).

We recommend the first or second option for final manuscripts and the third only for exploratory sweeps.

### F5. Figure caption hallucination

**Symptom.** VisualizationAgent occasionally writes figure captions that reference statistics not actually computed in the underlying script.

**Incidence.** ~5% of figures in early development. Mitigated by a tighter prompt (`bioagent/prompts/visualization.md`) that requires captions to reference only CSV columns that exist in the input data; current incidence ~1%.

### F6. Hypothesis testability drift

**Symptom.** The PlannerAgent sometimes proposes hypotheses with high novelty but low testability (novelty 9, testability 3) and still selects them when the rubric instructs it to balance both.

**Mitigation.** Selection logic in `bioagent/agents/planner.py` now uses `novelty + 1.5 * testability` rather than the sum, biasing toward actionable hypotheses. Post-fix, 0 observed selections with testability < 5.

### F7. Context-window overflow without review-loop gating

**Symptom.** When the ReviewAgent is ablated (see S3), the orchestrator cycles through phases without a terminal exit path. Tool-use messages accumulate in the conversation history until the Anthropic endpoint returns `invalid_request_error: context window exceeds limit`.

**Observed in.** The `no_review` ablation run for BRAF melanoma (S3.2.2) — crashed at wall-time 4,296 s during the AnalystAgent's second code-execution cycle, after 30 tool calls had accumulated in the message history.

**Incidence.** 0% of non-ablated runs; 100% of `no_review` runs beyond 60 minutes on current models.

**Mitigation.** Keep the ReviewAgent enabled (its cost-of-inclusion is modest relative to the catastrophic alternative). A planned enhancement is an explicit message-history compaction step triggered when conversation length exceeds 80% of the model window.

### F8. Windows-specific subprocess encoding errors

**Symptom.** `UnicodeDecodeError` when AnalystAgent subprocess output contains non-ASCII characters on Windows systems with GBK default encoding.

**Mitigation.** Every `subprocess.run` in the codebase pins `encoding="utf-8", errors="replace"`. No observed occurrence since this fix was applied in Phase 1. Covered by `tests/test_unit_tools.py::test_python_runner_handles_utf8`.

## S4.2 Severity Classification

| ID | Severity | Automatically recoverable | User intervention required |
|---|---|---|---|
| F1 | Moderate | No | Rephrase query |
| F2 | Low | Yes (fallback parser) | — |
| F3 | Low | Yes (retry) | — |
| F4 | Moderate | No | Raise budget or lower threshold |
| F5 | Low | Partially | Manual caption review |
| F6 | Low | Yes (selection heuristic) | — |
| F7 | High (in ablated config only) | No | Re-enable ReviewAgent, or wait for message-compaction feature |
| F8 | None (resolved) | Yes | — |

## S4.3 What Is *Not* Automatically Recoverable

Two categories of errors require human intervention:

1. **Gold-standard retrieval gaps (F1).** If the user's research question phrasing systematically under-retrieves canonical references, BioAgent will not detect this because it has no access to a ground-truth set at run time. The built-in benchmark evaluator catches this *post-hoc* but cannot prevent it *a priori*.

2. **Budget exhaustion (F4).** The ReviewAgent loop respects the token budget strictly. If a draft has not crossed the quality threshold before the budget runs out, the system exports the current draft and labels it `review_score < threshold` in the provenance log. The user must decide whether to raise the budget and rerun.

Both are documented in `README.md` and the usage docs.
