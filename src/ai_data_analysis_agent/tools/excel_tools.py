import ast
import builtins
import logging
import multiprocessing
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from ai_data_analysis_agent.core.session_store import get_file_path
from ai_data_analysis_agent.core.llm import call_llm
from ai_data_analysis_agent.core.config import Settings

logger = logging.getLogger(__name__)


MAX_RESULT_CHARS = 4000
MAX_ROWS_IN_RESULT = 200
CODE_EXEC_TIMEOUT_SECONDS = 10
CODE_EXEC_MEMORY_LIMIT_BYTES = 1024 * 1024 * 1024  # 1 GB
CODE_GEN_MAX_ATTEMPTS = 2

# ---------------------------------------------------------------------------
# File resolution + dataframe caching
# ---------------------------------------------------------------------------


class _DataFrameCache:
    """Caches (file_path, sheet_name) -> DataFrame, invalidated on file mtime change."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, Optional[str]], tuple[float, pd.DataFrame]] = {}

    def get(self, file_path: str, sheet_name: Optional[str]) -> pd.DataFrame:
        key = (file_path, sheet_name)
        mtime = Path(file_path).stat().st_mtime

        cached = self._cache.get(key)
        if cached is not None and cached[0] == mtime:
            return cached[1].copy(deep=True)

        df = pd.read_excel(file_path, sheet_name=sheet_name)
        if isinstance(df, dict):
            # sheet_name was None and the file had multiple sheets; default to the first.
            df = next(iter(df.values()))

        self._cache[key] = (mtime, df)
        return df.copy(deep=True)


_df_cache = _DataFrameCache()


def resolve_file_path(config: RunnableConfig) -> str:
    """Resolve the Excel file path for the current session from run config."""
    session = (config or {}).get("configurable", {})
    session_id = session.get("session_id")
    data_source = session.get("data_source")

    if data_source == "[Example] Sales Excel":
        path = Path(Settings.EXAMPLE_FILE)
        if not path.exists():
            raise FileNotFoundError(f"Example file missing at {Settings.EXAMPLE_FILE}")
        return str(path)

    if data_source == "Upload Excel":
        if not session_id:
            raise ValueError(
                "No session_id found in config; cannot resolve uploaded file."
            )
        file_path = get_file_path(session_id)
        if not file_path or not Path(file_path).exists():
            raise ValueError(
                "No file uploaded for this session, or the file is missing on disk."
            )
        return file_path

    raise ValueError(f"Invalid or missing Excel data_source: {data_source!r}")


def load_dataframe(file_path: str, sheet_name: Optional[str] = None) -> pd.DataFrame:
    """Load (and cache) a dataframe for a given file/sheet."""
    return _df_cache.get(file_path, sheet_name)


# ---------------------------------------------------------------------------
# Simple, low-risk tools
# ---------------------------------------------------------------------------


@tool
def excel_list_sheets(config: RunnableConfig) -> str:
    """List all sheet names available in the user's Excel file."""
    logger.info("Sheet listing started")
    try:
        file_path = resolve_file_path(config)
        with pd.ExcelFile(file_path) as xls:
            sheets = xls.sheet_names

        if not sheets:
            logger.info("No sheets found in workbook")
            return "The workbook contains no sheets."

        logger.info(f"Sheet listing completed ({len(sheets)} sheets found)")
        return "Sheets: " + ", ".join(sheets)
    except Exception as e:
        logger.exception("Sheet listing failed")
        return f"Error: {e}"


@tool
def excel_schema(config: RunnableConfig, sheet_name: Optional[str] = None) -> str:
    """
    Get column names, dtypes, null counts, and sample values for a sheet.

    Args:
        sheet_name: Name of the sheet to inspect. If omitted, the first sheet is used.
    """
    logger.info(f"Schema inspection started for sheet: {sheet_name or '(first sheet)'}")
    try:
        file_path = resolve_file_path(config)
        df = load_dataframe(file_path, sheet_name)

        logger.debug(f"Columns found: {list(df.columns)}")

        lines = [
            f"Schema for sheet: {sheet_name or '(first sheet)'}",
            f"Rows: {len(df)}",
            "",
        ]
        for col in df.columns:
            dtype = str(df[col].dtype)
            n_null = int(df[col].isna().sum())
            sample = df[col].dropna().astype(str).head(3).tolist()
            lines.append(f"- {col} | dtype={dtype} | nulls={n_null} | sample={sample}")

        logger.info(
            f"Schema inspection completed for {sheet_name or '(first sheet)'} "
            f"({len(df.columns)} columns, {len(df)} rows)"
        )
        return "\n".join(lines)
    except Exception as e:
        logger.exception(f"Schema inspection failed for sheet: {sheet_name}")
        return f"Error: {e}"


# ---------------------------------------------------------------------------
# Sandboxed code generation + execution
# ---------------------------------------------------------------------------

_CODE_GEN_PROMPT_TEMPLATE = """You are a pandas expert.

Given a dataframe `df`, write Python pandas code to answer:

{instruction}

Rules:
- Only use pandas via the pre-imported `pd` and pre-loaded `df`
- Do not import anything
- Do not modify `df` in place; create new variables
- Do not read or write any files, and do not access the network
- Store the final answer in a variable named `result`
- No plotting

Return ONLY the Python code. No explanation, no markdown fences.
"""

# Builtins that are safe to expose inside the sandboxed exec.
_ALLOWED_BUILTIN_NAMES = {
    "abs",
    "all",
    "any",
    "bool",
    "dict",
    "enumerate",
    "filter",
    "float",
    "int",
    "len",
    "list",
    "map",
    "max",
    "min",
    "range",
    "reversed",
    "round",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
    "zip",
}

# Names that must never appear in generated code, whether as identifiers or calls.
_FORBIDDEN_NAMES = {
    "__import__",
    "eval",
    "exec",
    "compile",
    "open",
    "input",
    "getattr",
    "setattr",
    "delattr",
    "globals",
    "locals",
    "vars",
    "dir",
    "help",
    "exit",
    "quit",
    "breakpoint",
    "memoryview",
    "os",
    "sys",
    "subprocess",
}

# DataFrame/Series methods that write data out or otherwise escape the sandbox.
_FORBIDDEN_ATTRS = {
    "to_csv",
    "to_excel",
    "to_pickle",
    "to_sql",
    "to_json",
    "to_parquet",
    "to_feather",
    "to_hdf",
    "to_clipboard",
}


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def _validate_code(code: str) -> None:
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
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            raise ValueError(f"Use of '{node.id}' is not allowed.")
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                raise ValueError("Access to dunder attributes is not allowed.")
            if node.attr in _FORBIDDEN_ATTRS:
                raise ValueError(
                    f"Call to '{node.attr}' is not allowed (no file/network I/O)."
                )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _FORBIDDEN_NAMES:
                raise ValueError(f"Call to '{node.func.id}' is not allowed.")


def _restricted_globals(df: pd.DataFrame) -> dict:
    safe_builtins = {name: getattr(builtins, name) for name in _ALLOWED_BUILTIN_NAMES}
    return {"__builtins__": safe_builtins, "pd": pd, "df": df}


def _execute_in_subprocess(
    code: str, df: pd.DataFrame, result_queue: "multiprocessing.Queue"
) -> None:
    """Runs inside an isolated child process. Never raises across the process boundary."""
    try:
        try:
            import resource  # POSIX only

            cpu = CODE_EXEC_TIMEOUT_SECONDS
            resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
            resource.setrlimit(
                resource.RLIMIT_AS,
                (CODE_EXEC_MEMORY_LIMIT_BYTES, CODE_EXEC_MEMORY_LIMIT_BYTES),
            )
        except (ImportError, ValueError, OSError):
            pass  # e.g. Windows, or limit not settable in this environment

        exec_globals = _restricted_globals(df)
        exec_locals: dict[str, Any] = {}
        exec(
            compile(code, "<generated>", "exec"), exec_globals, exec_locals
        )  # noqa: S102

        result = exec_locals.get("result", "No `result` variable was produced.")

        if isinstance(result, pd.DataFrame):
            if len(result) > MAX_ROWS_IN_RESULT:
                text = (
                    result.head(MAX_ROWS_IN_RESULT).to_string()
                    + f"\n... ({len(result) - MAX_ROWS_IN_RESULT} more rows truncated)"
                )
            else:
                text = result.to_string()
        else:
            text = str(result)

        if len(text) > MAX_RESULT_CHARS:
            text = text[:MAX_RESULT_CHARS] + "... (truncated)"

        result_queue.put(("ok", text))
    except Exception as e:  # report failure back instead of crashing silently
        result_queue.put(("error", f"{type(e).__name__}: {e}"))


def _run_generated_code(code: str, df: pd.DataFrame) -> str:
    _validate_code(code)

    try:
        ctx = multiprocessing.get_context("fork")
    except ValueError:
        ctx = multiprocessing.get_context("spawn")

    queue = ctx.Queue()
    proc = ctx.Process(target=_execute_in_subprocess, args=(code, df, queue))
    proc.start()
    proc.join(timeout=CODE_EXEC_TIMEOUT_SECONDS + 2)

    if proc.is_alive():
        proc.terminate()
        proc.join()
        raise TimeoutError(
            f"Code execution exceeded {CODE_EXEC_TIMEOUT_SECONDS}s and was terminated."
        )

    if queue.empty():
        raise RuntimeError(
            "Execution ended without a result (the process likely crashed)."
        )

    status, payload = queue.get()
    if status == "error":
        raise RuntimeError(payload)
    return payload


@tool
def run_excel_pipeline(instruction: str, config: RunnableConfig) -> str:
    """
    Analyze the current Excel sheet using pandas, generated on the fly from a
    natural-language instruction (e.g. "total sales by region").

    Args:
        instruction: The analysis question to answer, in plain English.
    """
    logger.info(f"Excel pipeline started. Instruction: {instruction}")
    try:
        file_path = resolve_file_path(config)
        df = load_dataframe(file_path)
    except Exception as e:
        logger.exception("Excel pipeline failed to load data")
        return f"Error loading data: {e}"

    last_error: Optional[str] = None
    for attempt in range(CODE_GEN_MAX_ATTEMPTS):
        logger.info(f"Code generation attempt {attempt + 1}/{CODE_GEN_MAX_ATTEMPTS}")
        prompt = _CODE_GEN_PROMPT_TEMPLATE.format(instruction=instruction)
        if last_error:
            prompt += f"\nYour previous attempt failed with: {last_error}\nFix the code and try again.\n"

        try:
            raw_code = call_llm(prompt)
            code = _strip_code_fences(raw_code)
            logger.debug(f"Generated code:\n{code}")

            result = _run_generated_code(code, df)
            logger.info(f"Excel pipeline completed on attempt {attempt + 1}")
            return result
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            last_error = str(e)

    logger.error(
        f"Excel pipeline exhausted {CODE_GEN_MAX_ATTEMPTS} attempts. Last error: {last_error}"
    )
    return f"Error: could not produce a valid analysis after {CODE_GEN_MAX_ATTEMPTS} attempts. Last error: {last_error}"
