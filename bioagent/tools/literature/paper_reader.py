"""Paper reading and summarization tools — LLM-based analysis of paper content."""

from __future__ import annotations

import logging

from bioagent.tools.registry import registry

logger = logging.getLogger(__name__)


def summarize_text(
    text: str,
    focus: str = "key findings, methodology, and limitations",
    max_length: int = 500,
) -> str:
    """Summarize a block of scientific text using the LLM.

    This is a lightweight helper — it calls the LLM directly (no tool loop)
    to produce a concise summary.

    Parameters
    ----------
    text : str
        Paper abstract or full text to summarize.
    focus : str
        What to focus the summary on.
    max_length : int
        Approximate max length of the summary in characters.
    """
    if len(text) < 100:
        return text

    try:
        from bioagent.llm.clients import get_anthropic_client, get_anthropic_model

        client = get_anthropic_client()
        model = get_anthropic_model()

        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=(
                "You are a scientific paper summarizer. "
                "Produce concise, structured summaries focusing on: "
                "1) Key findings/contributions, 2) Methods used, "
                "3) Limitations, 4) Relevance to bioinformatics research. "
                "Be precise and use domain-appropriate terminology."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Summarize the following text, focusing on {focus}.\n"
                        f"Keep it under {max_length} characters.\n\n"
                        f"---\n{text}\n---"
                    ),
                }
            ],
        )

        parts = [b.text for b in response.content if hasattr(b, "text")]
        return "\n".join(parts) if parts else text[:max_length]

    except Exception as exc:
        logger.warning("LLM summarization failed, returning truncated text: %s", exc)
        return text[:max_length]


def extract_key_entities(text: str) -> str:
    """Extract genes, diseases, drugs, and methods from scientific text.

    Parameters
    ----------
    text : str
        Scientific text (abstract or full paper section).
    """
    try:
        from bioagent.llm.clients import get_anthropic_client, get_anthropic_model

        client = get_anthropic_client()
        model = get_anthropic_model()

        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=(
                "Extract biomedical entities from the text. "
                "Return a structured list with categories:\n"
                "- Genes/Proteins\n"
                "- Diseases/Conditions\n"
                "- Drugs/Compounds\n"
                "- Methods/Technologies\n"
                "- Pathways\n\n"
                "Only include entities explicitly mentioned. "
                "Format as markdown lists."
            ),
            messages=[
                {
                    "role": "user",
                    "content": f"Extract key entities from:\n\n{text}",
                }
            ],
        )

        parts = [b.text for b in response.content if hasattr(b, "text")]
        return "\n".join(parts) if parts else "No entities extracted."

    except Exception as exc:
        logger.warning("Entity extraction failed: %s", exc)
        return f"Entity extraction failed: {exc}"


def register_tools() -> None:
    """Register paper analysis tools."""
    registry.register(
        name="summarize_text",
        description="Summarize scientific text (abstract or full paper). Focus on key findings, methodology, and limitations.",
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to summarize (abstract, section, or full paper)"},
                "focus": {
                    "type": "string",
                    "description": "What to focus on (e.g. 'key findings and methodology')",
                    "default": "key findings, methodology, and limitations",
                },
                "max_length": {
                    "type": "integer",
                    "description": "Approximate max summary length in chars",
                    "default": 500,
                },
            },
            "required": ["text"],
        },
        function=summarize_text,
    )
    registry.register(
        name="extract_key_entities",
        description="Extract genes, diseases, drugs, methods, and pathways from scientific text.",
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Scientific text to analyze"},
            },
            "required": ["text"],
        },
        function=extract_key_entities,
    )
