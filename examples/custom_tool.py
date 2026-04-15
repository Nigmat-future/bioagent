"""How to register a custom tool and use it from an agent.

This example adds a genome browser tool that fetches genomic coordinates
from Ensembl REST API and makes them available to the AnalystAgent.
"""

from __future__ import annotations

import json
import urllib.request
from bioagent.tools.registry import registry


def get_ensembl_coordinates(gene_symbol: str, species: str = "human") -> str:
    """Fetch genomic coordinates for a gene from the Ensembl REST API.

    Parameters
    ----------
    gene_symbol : str
        HGNC gene symbol (e.g. "BRAF", "TP53").
    species : str
        Species name (default: "human").

    Returns
    -------
    str
        JSON string with chromosome, start, end, strand, and Ensembl ID.
    """
    # Species name map
    species_map = {"human": "homo_sapiens", "mouse": "mus_musculus"}
    species_key = species_map.get(species.lower(), species.lower())

    url = f"https://rest.ensembl.org/lookup/symbol/{species_key}/{gene_symbol}"
    headers = {"Content-Type": "application/json"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return json.dumps({
            "gene_symbol": gene_symbol,
            "ensembl_id": data.get("id"),
            "chromosome": data.get("seq_region_name"),
            "start": data.get("start"),
            "end": data.get("end"),
            "strand": data.get("strand"),
            "biotype": data.get("biotype"),
            "description": data.get("description", "")[:200],
        }, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc), "gene_symbol": gene_symbol})


def register_genome_browser_tool() -> None:
    """Register the Ensembl coordinate tool into the global registry."""
    if "get_ensembl_coordinates" in registry.list_tools():
        return
    registry.register(
        name="get_ensembl_coordinates",
        description=(
            "Fetch genomic coordinates (chromosome, start, end, strand) for a gene "
            "from the Ensembl REST API. Returns Ensembl gene ID and biotype."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "gene_symbol": {
                    "type": "string",
                    "description": "HGNC gene symbol (e.g. 'BRAF', 'TP53')",
                },
                "species": {
                    "type": "string",
                    "description": "Species: 'human' or 'mouse' (default: 'human')",
                    "default": "human",
                },
            },
            "required": ["gene_symbol"],
        },
        function=get_ensembl_coordinates,
    )


# ── Usage from within AnalystAgent.get_tools() ────────────────────────────────
#
# Override get_tools() in a subclass:
#
#   class EnhancedAnalystAgent(AnalystAgent):
#       def get_tools(self):
#           tools, funcs = super().get_tools()
#           from examples.custom_tool import register_genome_browser_tool
#           register_genome_browser_tool()
#           extra_names = ["get_ensembl_coordinates"]
#           extra_defs = registry.get_definitions(extra_names)
#           extra_funcs = registry.get_functions(extra_names)
#           return tools + extra_defs, {**funcs, **extra_funcs}


if __name__ == "__main__":
    # Quick test
    register_genome_browser_tool()
    result = get_ensembl_coordinates("BRAF")
    print(result)
