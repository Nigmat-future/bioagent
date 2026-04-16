#!/usr/bin/env bash
# Reproduce the BRAF V600E melanoma benchmark from a clean environment.
#
# Usage:
#   scripts/reproduce_benchmark.sh            # full run (~3h, ~$0.40 glm-5.1)
#   scripts/reproduce_benchmark.sh --dry-run  # skip LLM calls; verify wiring only
#   scripts/reproduce_benchmark.sh --case all # run all 3 benchmark cases

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DRY_RUN=0
CASE="braf_melanoma"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=1; shift ;;
        --case) CASE="$2"; shift 2 ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

echo "==> BioAgent reproducibility runner"
echo "    root:   $ROOT"
echo "    case:   $CASE"
echo "    dryrun: $DRY_RUN"

if [[ ! -f requirements-lock.txt ]]; then
    echo "ERROR: requirements-lock.txt missing" >&2
    exit 1
fi

if ! python -c "import bioagent" 2>/dev/null; then
    echo "==> Installing locked dependencies"
    pip install -r requirements-lock.txt
    pip install -e .
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "==> Dry-run: compile graph, no LLM calls"
    python -c "
from bioagent.graph.research_graph import compile_research_graph
g = compile_research_graph()
nodes = list(g.get_graph().nodes)
assert 'data_acquisition' in nodes, 'data_acquisition node missing'
print('Graph compiled with', len(nodes), 'nodes:', nodes)
"
    echo "==> Dry-run OK"
    exit 0
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" ]] && [[ ! -f .env ]]; then
    echo "ERROR: ANTHROPIC_API_KEY unset and .env missing" >&2
    exit 1
fi

echo "==> Running benchmark (seed=42)"
export BIOAGENT_RANDOM_SEED=42
python benchmarks/run_benchmark.py --case "$CASE" --output benchmarks/results

EXPECTED_HASH_FILE="benchmarks/expected_hashes.json"
if [[ -f "$EXPECTED_HASH_FILE" ]]; then
    echo "==> Verifying output hashes"
    python scripts/verify_hashes.py "$EXPECTED_HASH_FILE" "benchmarks/results/$CASE"
else
    echo "==> (No expected_hashes.json; skipping hash verification)"
fi

echo "==> Reproduction complete. Outputs in benchmarks/results/$CASE/"
