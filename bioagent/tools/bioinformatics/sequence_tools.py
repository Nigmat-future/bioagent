"""Bioinformatics tool interfaces — code generation helpers for the AnalystAgent.

These tools don't execute directly — they return Python code snippets that the
analyst agent can incorporate into its scripts.
"""

from __future__ import annotations

from bioagent.tools.registry import registry


def get_sequence_analysis_template(analysis_type: str) -> str:
    """Get a code template for common sequence analysis tasks.

    Parameters
    ----------
    analysis_type : str
        Type of analysis: "blast", "alignment", "orf_finding", "gc_content"
    """
    templates = {
        "blast": '''# BLAST search using BioPython
from Bio.Blast import NCBIWWW, NCBIXML

def run_blast(sequence, program="blastn", database="nt", expect=0.001):
    """Run BLAST search against NCBI."""
    result_handle = NCBIWWW.qblast(program, database, sequence, expect=expect)
    blast_records = NCBIXML.parse(result_handle)
    results = []
    for record in blast_records:
        for alignment in record.alignments:
            for hsp in alignment.hsps:
                results.append({
                    "title": alignment.title,
                    "e_value": hsp.expect,
                    "score": hsp.score,
                    "identity": hsp.identities / hsp.align_length,
                })
    return results
''',
        "alignment": '''# Sequence alignment using BioPython
from Bio import Align
from Bio.Seq import Seq

def align_sequences(seq1, seq2, mode="global"):
    """Align two sequences."""
    aligner = Align.PairwiseAligner()
    aligner.mode = mode
    alignments = aligner.align(seq1, seq2)
    best = alignments[0]
    return {
        "aligned_seq1": str(best).split("\\n")[0],
        "aligned_seq2": str(best).split("\\n")[-1],
        "score": best.score,
    }
''',
        "gc_content": '''# GC content calculation
from Bio.SeqUtils import gc_fraction

def calculate_gc_content(sequence):
    """Calculate GC content of a sequence."""
    return gc_fraction(sequence) * 100

def gc_content_sliding_window(sequence, window_size=100):
    """Calculate GC content in sliding windows."""
    results = []
    for i in range(0, len(sequence) - window_size + 1, window_size // 2):
        window = sequence[i:i + window_size]
        gc = gc_fraction(window) * 100
        results.append({"position": i, "gc_content": gc})
    return results
''',
    }
    return templates.get(analysis_type, f"# Template for '{analysis_type}' not found")


def register_tools() -> None:
    if "get_sequence_analysis_template" in registry.list_tools():
        return
    registry.register(
        name="get_sequence_analysis_template",
        description="Get Python code templates for sequence analysis (BLAST, alignment, GC content).",
        input_schema={
            "type": "object",
            "properties": {
                "analysis_type": {
                    "type": "string",
                    "description": "Analysis type: blast, alignment, orf_finding, gc_content",
                },
            },
            "required": ["analysis_type"],
        },
        function=get_sequence_analysis_template,
    )
