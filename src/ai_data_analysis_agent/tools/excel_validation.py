"""
Pure validation logic for LLM-generated pandas code.

Deliberately has ZERO project-internal imports (only stdlib + pandas) and no
side effects at import time. This is what makes it safe to unit test
directly, independent of session/config/LLM wiring.
"""

from __future__ import annotations

import ast
import builtins

import pandas as pd

from ai_data_analysis_agent.core.text_utils import strip_code_fences  # noqa: F401 (re-exported)

# Builtins that are safe to expose inside the sandboxed exec.
ALLOWED_BUILTIN_NAMES = {
    "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
    "int", "len", "list", "map", "max", "min", "range", "reversed",
    "round", "set", "sorted", "str", "sum", "tuple", "zip",
}

# Names that must never appear in generated code, whether as identifiers or calls.
FORBIDDEN_NAMES = {
    "__import__", "eval", "exec", "compile", "open", "input",
    "getattr", "setattr", "delattr", "globals", "locals", "vars",
    "dir", "help", "exit", "quit", "breakpoint", "memoryview", "os", "sys", "subprocess",
}

# DataFrame/Series methods that write data out or otherwise escape the sandbox.
FORBIDDEN_ATTRS = {
    "to_csv", "to_excel", "to_pickle", "to_sql", "to_json", "to_parquet",
    "to_feather", "to_hdf", "to_clipboard",
}


def validate_code(code: str) -> None:
    """Raise ValueError if generated code contains anything disallowed."""
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as e:
        raise ValueError(f"Generated code has a syntax error: {e}") from e

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValueError("Generated code may not import modules.")
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            raise ValueError("Generated code may not use global/nonlocal.")
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise ValueError(f"Use of '{node.id}' is not allowed.")
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                raise ValueError("Access to dunder attributes is not allowed.")
            if node.attr in FORBIDDEN_ATTRS:
                raise ValueError(f"Call to '{node.attr}' is not allowed (no file/network I/O).")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_NAMES:
                raise ValueError(f"Call to '{node.func.id}' is not allowed.")


def restricted_globals(df: pd.DataFrame) -> dict:
    safe_builtins = {name: getattr(builtins, name) for name in ALLOWED_BUILTIN_NAMES}
    return {"__builtins__": safe_builtins, "pd": pd, "df": df}