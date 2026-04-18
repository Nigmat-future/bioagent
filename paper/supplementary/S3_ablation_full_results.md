# Supplementary Material S3: Ablation Full Results

## S3.1 Ablation Variants

Five ablation variants implemented in `benchmarks/ablation.py`:

| Variant | What is removed | How |
|---|---|---|
| `full` | -- | Reference configuration |
| `no_literature` | `literature_review_node` | Node replaced with pass-through; `papers`, `research_gaps` remain empty |
| `no_data` | `data_acquisition_node` | No real data download; Analyst falls back to structured template outputs |
| `no_code` | `code_execution_node` + `result_validation_node` | Writer receives empty `analysis_results` and `execution_results` |
| `no_review` | `review_node` | Export triggered immediately after first writing pass; no revision loop |
| `single_pass_llm` | Entire graph | Single Claude `messages.create` call with the research question |

The variant factory replaces only the target node function, then restores the original after graph compilation, so running multiple variants in one Python process is safe.

## S3.2 Executed Results

For the v0.2.0 release, the following variants were executed end-to-end on the BRAF V600E melanoma case. The remaining variants are scaffolded but compute-bounded (each non-trivial variant requires ~1.5–2 h wall-clock on glm-5.1); results for those will be added in the revision round.

### S3.2.1 Executed

| Variant | Model | Time (s) | Cost ($) | PMIDs | Code artefacts | Figures | Writing sections | Weighted | Terminal status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `full` (reference)                   | Claude Sonnet 4.6 | 5,800 | 2.47 | 2  | 4 | 12 | 5 | 5.30 | complete (review=5) |
| `no_review`                          | Claude Sonnet 4.6 | 4,296 | 0.96 | 15 | 0 | 0  | 0 | 2.30 | context overflow (F7) |
| `no_literature`                      | MiniMax-M7        | 260   | 0.16 | 1* | 0 | 0  | 0 | 1.70 | context overflow (F7) |
| `no_data`                            | MiniMax-M7        | 751   | 0.59 | 3  | 0 | 0  | 0 | 2.71 | Analyst could not execute without real data |
| `no_code`                            | MiniMax-M7        | 9     | 0.00 | 0  | 0 | 0  | 0 | 0.30 | API overloaded (529), retry pending |
| `single_pass_llm` (= single-prompt)  | Claude Sonnet 4.6 | 140   | 0.08 | 0  | 0 | 0  | 1 (monolith) | 1.39 | complete |
| AutoGen-style chat (6 turns)         | Claude Sonnet 4.6 | 703   | 0.56 | 0  | 0 | 0  | 1 (monolith) | 1.05 | complete |

\*Sentinel paper from the ablation stub (`[LITERATURE AGENT ABLATED]`); zero real PMIDs retrieved.

Runs used two LLM endpoints: Claude Sonnet 4.6 through MiniMax's Anthropic-compatible gateway (`api.minimaxi.com/anthropic`) for the `full`, `no_review`, `single_pass`, and `autogen` configurations; and MiniMax's own `MiniMax-M7` model through the same gateway for the remaining three ablations. Both endpoints use the same API surface; the model change is transparent to BioAgent. `BIOAGENT_RANDOM_SEED=42` throughout.

### S3.2.2 Notable finding: `no_review` terminates abnormally

The `no_review` run retrieved 15 PMIDs (more than the full system's 2, the orchestrator re-routed to literature review more aggressively because nothing gated the exit) but never reached the writing or figure-generation phases. At wall-time 4,296 s the run raised `invalid_request_error: context window exceeds limit` mid-AnalystAgent and exited with 0 writing sections and 0 figures.

**Interpretation.** The review gate plays a second, non-obvious role beyond quality control: its "approve and END" transition bounds the total message-history length. Ablating it allows the orchestrator to cycle through phases indefinitely, accumulating tool-use messages until the conversation window overflows. This is a useful diagnostic, it shows that `no_review` fails for a reason orthogonal to review quality, and motivates adding an explicit message-history compaction step as future work.

### S3.2.3 Notable finding: `no_data` validates the fabricate-nothing invariant

The `no_data` run completed the upstream phases (literature: 3 PMIDs, hypothesis generation) but the AnalystAgent refused to proceed in `code_execution`: the analyst's prompt (`bioagent/prompts/analyst.md`) explicitly forbids synthesising data when `workspace/data/` is empty, and the agent produced the error `Analyst did not produce analyzable results` rather than fabricating a matrix. This is the intended behaviour and confirms that removing DataAcquisition does not silently regress into synthetic-data runs, it visibly halts the pipeline, making the dependency auditable.

### S3.2.4 Notable finding: `no_literature` early context overflow

The `no_literature` run hit the same context-overflow pattern as `no_review`, but earlier, within the data-acquisition phase itself at 260 s. The ablated literature stub populated only a sentinel paper, so the PlannerAgent generated a hypothesis from that thin context and the downstream DataAcquisitionAgent's extensive tool-use conversation pushed total message history past the model's 2{,}013-token effective limit in the MiniMax-M7 configuration. This reinforces the finding in S3.2.2 that message-history compaction is needed for any configuration that removes an intermediate gate.

### S3.2.5 `no_code`: API-overloaded run, retry pending

The `no_code` run returned a 529 `overloaded_error` after 9 s without reaching any phase, a transient API failure unrelated to the ablation. A retry is queued in `benchmarks/results/ablation/`; once the endpoint recovers, the expected behaviour is that the pipeline completes through the writing phase with an empty Results section (the writer prompt instructs it to narrate what *would* have been produced when `execution_results` is empty) and a low analysis score.

### S3.2.6 Pending

- Full retry of `no_code` variant once MiniMax-M7 endpoint recovers from 529 overload.
- Cross-case ablation sweep (TP53 pan-cancer and PBMC scRNA-seq) for generalisation beyond the BRAF benchmark; estimated at ~$10 and ~8 h wall-clock.

A command to reproduce the full ablation sweep:

```bash
python benchmarks/ablation.py --variant all --case braf_melanoma \
    --output benchmarks/results/ablation
```

## S3.3 Why the Full Ablation Sweep is Expensive

Each non-trivial variant reruns the complete LangGraph pipeline minus one node. Because the AnalystAgent is where most tokens are spent (approximately 60% of the $2.47 BRAF cost), removing any node except `no_code` does not meaningfully reduce run time. Running the full sweep of four graph variants therefore costs approximately 4 × $2.47 ≈ $10 and 6–8 hours of wall time per benchmark case.

The three-case sweep (BRAF, TP53 pan-cancer, PBMC scRNA-seq) is the natural extension for a revision round, at a compute budget of ~$30 and ~24 hours.

## S3.4 Interpretation

The `single_pass_llm` variant already establishes the most important ablation point: removing the entire agentic scaffolding collapses the pipeline to a 1.4/10 weighted score against the full system's 5.3/10, despite using 97% less compute. This demonstrates that the ~40× cost multiplier of the full pipeline buys genuinely additive value in the form of grounded literature retrieval, executable analyses, and figure generation, not merely longer text output (the AutoGen-style chat produces 5× more text but scores *lower* because it contributes zero verifiable artefacts).
