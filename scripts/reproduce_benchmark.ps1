# Reproduce the BRAF V600E melanoma benchmark on Windows PowerShell.
# Usage:
#   scripts\reproduce_benchmark.ps1
#   scripts\reproduce_benchmark.ps1 -DryRun
#   scripts\reproduce_benchmark.ps1 -Case all

param(
    [switch]$DryRun,
    [string]$Case = "braf_melanoma"
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

Write-Host "==> BioAgent reproducibility runner"
Write-Host "    root:   $Root"
Write-Host "    case:   $Case"
Write-Host "    dryrun: $DryRun"

if (-not (Test-Path "requirements-lock.txt")) {
    Write-Error "requirements-lock.txt missing"
    exit 1
}

python -c "import bioagent" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "==> Installing locked dependencies"
    pip install -r requirements-lock.txt
    pip install -e .
}

if ($DryRun) {
    Write-Host "==> Dry-run: compile graph, no LLM calls"
    python -c "from bioagent.graph.research_graph import compile_research_graph; g = compile_research_graph(); nodes = list(g.get_graph().nodes); assert 'data_acquisition' in nodes; print('Graph OK:', len(nodes), 'nodes')"
    Write-Host "==> Dry-run OK"
    exit 0
}

if (-not $env:ANTHROPIC_API_KEY -and -not (Test-Path ".env")) {
    Write-Error "ANTHROPIC_API_KEY unset and .env missing"
    exit 1
}

Write-Host "==> Running benchmark (seed=42)"
$env:BIOAGENT_RANDOM_SEED = "42"
python benchmarks/run_benchmark.py --case $Case --output benchmarks/results

if (Test-Path "benchmarks/expected_hashes.json") {
    Write-Host "==> Verifying output hashes"
    python scripts/verify_hashes.py "benchmarks/expected_hashes.json" "benchmarks/results/$Case"
}

Write-Host "==> Reproduction complete. Outputs in benchmarks/results/$Case/"
