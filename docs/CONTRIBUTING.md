# Contributing to BioAgent

Thank you for considering a contribution. This document covers the practical setup, testing, and review process.

## Development setup

```bash
git clone https://github.com/nigmatrahim/bioagent.git
cd bioagent
pip install -e ".[dev]"
pre-commit install
```

Create a `.env` file based on `.env.example`, set your `BIOAGENT_ANTHROPIC_API_KEY`, and run the smoke test:

```bash
python -c "from bioagent.graph.research_graph import compile_research_graph; compile_research_graph()"
```

## Running tests

```bash
# Fast suite (no network; default CI target)
pytest tests/ -m "not api and not slow"

# Full suite (requires API key and several minutes)
pytest tests/ -v

# With coverage
pytest tests/ -m "not api and not slow" --cov=bioagent --cov-report=term-missing
```

## Code style

- **ruff** for linting and import sorting: `ruff check bioagent/` must pass.
- **mypy** for type-checking: `mypy bioagent/ --ignore-missing-imports` must pass (blocking in CI).
- Pre-commit hooks enforce this on every commit. If a hook modifies files, re-stage and recommit.

## Adding an agent

Subclass `bioagent.agents.base.BaseAgent`, implement `get_system_prompt`, `get_tools`, `build_messages`, and `process_result`, then wire it into `bioagent/graph/research_graph.py` and `bioagent/graph/nodes.py`. Add the new phase name to `bioagent.agents.orchestrator.VALID_PHASES` and `bioagent/prompts/orchestrator.md`. See `bioagent/agents/data_acquisition.py` for a concrete template.

## Adding a tool

Register new tools in a `bioagent/tools/<domain>/register.py` module with the idempotency pattern used by `bioagent/tools/data/register.py`. Input schemas must be valid JSON schema and directly compatible with the Anthropic tool-use API.

## Adding a benchmark case

Create `benchmarks/cases/<name>.py` with a `BenchmarkCase` dataclass instance, then add it to `benchmarks/cases/__init__.py::ALL_CASES`. Document the datasets and gold-standard PMIDs in `benchmarks/data/README.md`.

## Pull request checklist

- [ ] Branch is up to date with `main`.
- [ ] `pytest -m "not api and not slow"` passes.
- [ ] `ruff check bioagent/` passes.
- [ ] `mypy bioagent/` passes.
- [ ] New tests added for new logic (target ≥70% on changed files).
- [ ] CHANGELOG entry (if user-visible).
- [ ] No `.env`, credentials, or large binaries committed.
- [ ] Docstrings on new public APIs.

## Reporting bugs

Open an issue at <https://github.com/nigmatrahim/bioagent/issues> with:

1. BioAgent version (`pip show bioagent`).
2. Python version and OS.
3. Full traceback.
4. Minimal reproduction script.
5. Whether it happens with the lock-file environment (`pip install -r requirements-lock.txt`).

## Security

Please report security issues privately by email to `nigmatrahim@stu.pku.edu.cn` rather than as a public issue.

## Licence

By submitting code you agree to license it under the MIT licence, consistent with the rest of the project.
