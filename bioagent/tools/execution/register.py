"""Shared execution tool registration — ensures all execution tools are in the registry.

Both AnalystAgent and VisualizationAgent call register_execution_tools() from
get_tools() so that either agent can run independently regardless of initialization order.
"""

from __future__ import annotations


def register_execution_tools() -> None:
    """Register all execution and file tools into the global registry (idempotent)."""
    from bioagent.tools.execution.python_runner import execute_python
    from bioagent.tools.execution.package_manager import install_package
    from bioagent.tools.general.file_tools import read_file, write_file, list_files
    from bioagent.tools.registry import registry

    if "execute_python" not in registry.list_tools():
        registry.register(
            name="execute_python",
            description=(
                "Execute Python code in a subprocess and return output. "
                "Code runs in the workspace directory with a configurable timeout."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"},
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default 120, max 300)",
                        "default": 120,
                    },
                },
                "required": ["code"],
            },
            function=execute_python,
        )

    if "install_package" not in registry.list_tools():
        registry.register(
            name="install_package",
            description="Install a Python package via pip if not already installed.",
            input_schema={
                "type": "object",
                "properties": {
                    "package_name": {
                        "type": "string",
                        "description": "Package name (e.g. 'scanpy', 'scikit-learn')",
                    },
                },
                "required": ["package_name"],
            },
            function=install_package,
        )

    if "write_file" not in registry.list_tools():
        registry.register(
            name="write_file",
            description="Write content to a file in the workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relative to workspace (e.g. 'figures/plot.py')",
                    },
                    "content": {"type": "string", "description": "File content"},
                },
                "required": ["path", "content"],
            },
            function=write_file,
        )

    if "read_file" not in registry.list_tools():
        registry.register(
            name="read_file",
            description="Read a file from the workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relative to workspace",
                    },
                },
                "required": ["path"],
            },
            function=read_file,
        )

    if "list_files" not in registry.list_tools():
        registry.register(
            name="list_files",
            description="List files in a workspace directory.",
            input_schema={
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory path relative to workspace (empty for root)",
                        "default": "",
                    },
                },
            },
            function=list_files,
        )
