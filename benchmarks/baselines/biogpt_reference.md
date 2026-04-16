# BioGPT as a Capability Reference

We do **not** rerun BioGPT (Luo et al., 2022, *Briefings in Bioinformatics*) in our benchmarks, for two reasons:

1. **Scope mismatch.** BioGPT is a domain-adapted GPT-2 variant intended for single-prompt biomedical text generation. It has no tool use, no iteration, no multi-agent state, and no code execution. Comparing its single-prompt output against BioAgent's full pipeline on metrics like "datasets acquired" or "analyses executed" is not meaningful — BioGPT structurally cannot achieve non-zero scores.

2. **Published numbers available.** BioGPT's reported performance on biomedical text benchmarks (BC5CDR end-to-end relation extraction F1 = 44.98, PubMedQA accuracy = 81.0, HoC classification F1 = 85.12) is already in the literature. Where the paper compares coverage characteristics, we cite these reported values rather than re-running the model.

BioGPT's role in Table~1 of our manuscript is therefore a **capability matrix** entry, not a quantitative head-to-head.

## Capability summary (for Table 1)

| Capability | BioGPT | BioAgent |
|---|---|---|
| Biomedical-domain language model | ✓ | Uses frontier general-purpose LLM (Claude) |
| PubMed / ClinVar retrieval | ✗ | ✓ (via BioMCP) |
| Real data download (TCGA/GEO) | ✗ | ✓ (DataAcquisitionAgent) |
| Executable code generation | ✗ | ✓ (AnalystAgent with subprocess execution) |
| Iterative self-review | ✗ | ✓ (ReviewAgent gating loop) |
| Publication-ready LaTeX export | ✗ | ✓ (OUP format + BibTeX) |

## References

- Luo R., Sun L., Xia Y., *et al.* (2022). *BioGPT: Generative pre-trained transformer for biomedical text generation and mining.* Briefings in Bioinformatics 23(6):bbac409. PMID: 36433771.
