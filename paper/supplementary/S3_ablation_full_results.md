# Supplementary Material S3 — Ablation Full Results

## S3.1 Ablation Variants

Five ablation variants implemented in `benchmarks/ablation.py`:

| Variant | What is removed | How |
|---|---|---|
| `full` | — | Reference configuration |
| `no_literature` | `literature_review_node` | Node replaced with pass-through; `papers`, `research_gaps` remain empty |
| `no_data` | `data_acquisition_node` | No real data download; Analyst falls back to structured template outputs |
| `no_code` | `code_execution_node` + `result_validation_node` | Writer receives empty `analysis_results` and `execution_results` |
| `no_review` | `review_node` | Export triggered immediately after first writing pass; no revision loop |
| `single_pass_llm` | Entire graph | Single Claude `messages.create` call with the research question |

The variant factory replaces only the target node function, then restores the original after graph compilation, so running multiple variants in one Python process is safe.

## S3.2 Executed Results

For the v0.2.0 release, the following variants were executed end-to-end on the BRAF V600E melanoma case. The remaining variants are scaffolded but compute-bounded (each non-trivial variant requires ~1.5–2 h wall-clock on glm-5.1); results for those will be added in the revision round.

### S3.2.1 Executed

| Variant | Time (s) | Cost ($) | PMIDs | Code artefacts | Figures | Writing sections | Weighted |
|---|---:|---:|---:|---:|---:|---:|---:|
| `full` (reference) | 5,800 | 2.47 | 2 | 4 | 12 | 5 | 5.3 |
| `no_review` | 4,296 | 0.96 | 15 | 0 | 0 | 0 | 2.3 |
| `single_pass_llm` (= single-prompt) | 140 | 0.08 | 0 | 0 | 0 | 1 (monolith) | 1.39 |
| AutoGen-style chat (6 turns) | 703 | 0.56 | 0 | 0 | 0 | 1 (monolith) | 1.05 |

Executed with `BIOAGENT_RANDOM_SEED=42`, `claude-sonnet-4-6` endpoint via the glm-5.1 gateway.

### S3.2.2 Notable finding: `no_review` terminates abnormally

The `no_review` run retrieved 15 PMIDs (more than the full system's 2 — the orchestrator re-routed to literature review more aggressively because nothing gated the exit) but never reached the writing or figure-generation phases. At wall-time 4,296 s the run raised `invalid_request_error: context window exceeds limit` mid-AnalystAgent and exited with 0 writing sections and 0 figures.

**Interpretation.** The review gate plays a second, non-obvious role beyond quality control: its "approve and END" transition bounds the total message-history length. Ablating it allows the orchestrator to cycle through phases indefinitely, accumulating tool-use messages until the conversation window overflows. This is a useful diagnostic — it shows that `no_review` fails for a reason orthogonal to review quality, and motivates adding an explicit message-history compaction step as future work.

### S3.2.3 Pending (scaffolded but not yet executed)

- `no_literature` — expected behaviour: hypothesis quality drops because the PlannerAgent loses its literature-grounding input; novelty claims become unverifiable. Hypothesis score expected to fall from ~7.5 to ~3.
- `no_data` — expected behaviour: AnalystAgent still produces code but executes it on templated inputs; analysis score unchanged but biological grounding lost. Reviewer comment expected: "results rely on synthetic data".
- `no_code` — expected behaviour: Results section becomes narrative-only; writing completeness unchanged but analysis score = 0.

A command to reproduce the full ablation sweep:

```bash
python benchmarks/ablation.py --variant all --case braf_melanoma \
    --output benchmarks/results/ablation
```

## S3.3 Why the Full Ablation Sweep is Expensive

Each non-trivial variant reruns the complete LangGraph pipeline minus one node. Because the AnalystAgent is where most tokens are spent (approximately 60% of the $2.47 BRAF cost), removing any node except `no_code` does not meaningfully reduce run time. Running the full sweep of four graph variants therefore costs approximately 4 × $2.47 ≈ $10 and 6–8 hours of wall time per benchmark case.

The three-case sweep (BRAF, TP53 pan-cancer, PBMC scRNA-seq) is the natural extension for a revision round, at a compute budget of ~$30 and ~24 hours.

## S3.4 Interpretation

The `single_pass_llm` variant already establishes the most important ablation point: removing the entire agentic scaffolding collapses the pipeline to a 1.4/10 weighted score against the full system's 5.3/10, despite using 97% less compute. This demonstrates that the ~40× cost multiplier of the full pipeline buys genuinely additive value in the form of grounded literature retrieval, executable analyses, and figure generation — not merely longer text output (the AutoGen-style chat produces 5× more text but scores *lower* because it contributes zero verifiable artefacts).
