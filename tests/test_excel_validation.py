import pytest

from ai_data_analysis_agent.tools.excel_validation import strip_code_fences, validate_code


class TestValidateCode:
    def test_valid_simple_code_passes(self):
        validate_code("result = df['Revenue'].sum()")

    def test_valid_groupby_code_passes(self):
        validate_code("result = df.groupby('Region')['Revenue'].sum()")

    def test_syntax_error_raises(self):
        with pytest.raises(ValueError, match="syntax error"):
            validate_code("result = df[")

    def test_rejects_import(self):
        with pytest.raises(ValueError, match="import"):
            validate_code("import os\nresult = 1")

    def test_rejects_import_from(self):
        with pytest.raises(ValueError, match="import"):
            validate_code("from os import system\nresult = 1")

    def test_rejects_os_name(self):
        with pytest.raises(ValueError, match="not allowed"):
            validate_code("result = os.getcwd()")

    def test_rejects_subprocess_name(self):
        with pytest.raises(ValueError, match="not allowed"):
            validate_code("result = subprocess.run(['ls'])")

    def test_rejects_open(self):
        with pytest.raises(ValueError, match="not allowed"):
            validate_code("f = open('/etc/passwd')\nresult = f.read()")

    def test_rejects_eval(self):
        with pytest.raises(ValueError, match="not allowed"):
            validate_code("result = eval('1+1')")

    def test_rejects_exec(self):
        with pytest.raises(ValueError, match="not allowed"):
            validate_code("exec('x = 1')\nresult = 1")

    def test_rejects_dunder_import(self):
        with pytest.raises(ValueError, match="not allowed"):
            validate_code("result = __import__('os').getcwd()")

    def test_rejects_dunder_attribute_access(self):
        with pytest.raises(ValueError, match="dunder"):
            validate_code("result = df.__class__.__bases__")

    def test_rejects_getattr(self):
        with pytest.raises(ValueError, match="not allowed"):
            validate_code("result = getattr(df, 'to_csv')")

    def test_rejects_global(self):
        with pytest.raises(ValueError, match="global/nonlocal"):
            validate_code("def f():\n    global x\n    x = 1\nresult = f()")

    def test_rejects_to_csv(self):
        with pytest.raises(ValueError, match="to_csv"):
            validate_code("df.to_csv('out.csv')\nresult = 1")

    def test_rejects_to_pickle(self):
        with pytest.raises(ValueError, match="to_pickle"):
            validate_code("df.to_pickle('out.pkl')\nresult = 1")

    def test_rejects_to_sql(self):
        with pytest.raises(ValueError, match="to_sql"):
            validate_code("df.to_sql('t', None)\nresult = 1")

    def test_allows_safe_builtins(self):
        # len, sorted, sum etc. are legitimate and should not be flagged.
        validate_code("result = sorted(df['Product'].tolist())")
        validate_code("result = len(df)")
        validate_code("result = sum(df['Revenue'])")

    def test_rejects_dir_call(self):
        with pytest.raises(ValueError, match="not allowed"):
            validate_code("result = dir(df)")

    def test_rejects_vars_call(self):
        with pytest.raises(ValueError, match="not allowed"):
            validate_code("result = vars(df)")


class TestStripCodeFences:
    def test_no_fences_returns_unchanged(self):
        code = "result = df.sum()"
        assert strip_code_fences(code) == code

    def test_strips_plain_fences(self):
        raw = "```\nresult = df.sum()\n```"
        assert strip_code_fences(raw) == "result = df.sum()"

    def test_strips_language_tagged_fences(self):
        raw = "```python\nresult = df.sum()\n```"
        assert strip_code_fences(raw) == "result = df.sum()"

    def test_strips_surrounding_whitespace(self):
        raw = "  \n```python\nresult = df.sum()\n```\n  "
        assert strip_code_fences(raw) == "result = df.sum()"

    def test_multiline_code_inside_fences(self):
        raw = "```python\nx = 1\nresult = x + 1\n```"
        assert strip_code_fences(raw) == "x = 1\nresult = x + 1"
