import pytest

from ai_data_analysis_agent.tools.sql_validation import ensure_limit, validate_readonly_sql


class TestValidateReadonlySql:
    def test_simple_select_passes(self):
        result = validate_readonly_sql("SELECT * FROM tracks")
        assert result == "SELECT * FROM tracks"

    def test_select_with_where_passes(self):
        validate_readonly_sql("SELECT name, price FROM albums WHERE price > 10")

    def test_cte_with_clause_passes(self):
        # WITH ... SELECT queries were incorrectly rejected by the old
        # prefix-only check; CTEs are legitimate read-only queries.
        query = "WITH top AS (SELECT * FROM tracks) SELECT * FROM top"
        validate_readonly_sql(query)

    def test_trailing_semicolon_is_stripped(self):
        result = validate_readonly_sql("SELECT * FROM tracks;")
        assert result == "SELECT * FROM tracks"

    def test_empty_query_rejected(self):
        with pytest.raises(ValueError, match="No SQL statement"):
            validate_readonly_sql("")

    def test_whitespace_only_query_rejected(self):
        with pytest.raises(ValueError, match="No SQL statement"):
            validate_readonly_sql("   ")

    def test_multiple_statements_rejected(self):
        with pytest.raises(ValueError, match="single SQL statement"):
            validate_readonly_sql("SELECT * FROM tracks; SELECT * FROM albums;")

    def test_stacked_query_attack_rejected(self):
        # The classic injection pattern: a valid SELECT followed by a
        # destructive statement, hoping only the first gets validated.
        with pytest.raises(ValueError, match="single SQL statement"):
            validate_readonly_sql("SELECT * FROM tracks; DROP TABLE tracks;")

    @pytest.mark.parametrize(
        "keyword",
        ["insert", "update", "delete", "drop", "alter", "create", "replace",
         "attach", "detach", "pragma", "vacuum", "truncate"],
    )
    def test_rejects_forbidden_keyword_at_top_level(self, keyword):
        with pytest.raises(ValueError, match="Disallowed keyword"):
            validate_readonly_sql(f"{keyword} something")

    def test_rejects_delete_disguised_as_select_adjacent(self):
        with pytest.raises(ValueError, match="Disallowed keyword"):
            validate_readonly_sql("SELECT * FROM tracks WHERE 1=1; DELETE FROM tracks")

    def test_rejects_write_keyword_inside_cte(self):
        # A write statement hidden inside a CTE, relying on the outer
        # statement merely "starting with" SELECT/WITH to slip through.
        query = "WITH x AS (DELETE FROM tracks RETURNING *) SELECT * FROM x"
        with pytest.raises(ValueError, match="Disallowed keyword"):
            validate_readonly_sql(query)

    def test_rejects_non_select_statement(self):
        with pytest.raises(ValueError, match="Only SELECT statements"):
            validate_readonly_sql("EXPLAIN QUERY PLAN SELECT * FROM tracks")

    def test_column_name_containing_forbidden_substring_is_fine(self):
        # A column/table literally named e.g. "created_at" contains "create"
        # as a substring but is NOT the keyword "create" as its own token -
        # the tokenizer must not false-positive on substrings.
        validate_readonly_sql("SELECT created_at FROM tracks")

    def test_string_literal_containing_forbidden_keyword_is_fine(self):
        # A value like 'update the docs' should not trip the keyword scan,
        # since it's a string literal, not a SQL keyword token.
        validate_readonly_sql("SELECT * FROM notes WHERE body = 'please update the docs'")


class TestEnsureLimit:
    def test_adds_limit_when_missing(self):
        result = ensure_limit("SELECT * FROM tracks", limit=50)
        assert result == "SELECT * FROM tracks LIMIT 50"

    def test_does_not_duplicate_existing_limit(self):
        query = "SELECT * FROM tracks LIMIT 10"
        result = ensure_limit(query, limit=50)
        assert result == query
        assert result.upper().count("LIMIT") == 1

    def test_not_fooled_by_limit_substring_in_string_literal(self):
        # A naive substring check ("limit" in query.lower()) would wrongly
        # skip adding LIMIT here, since the word appears inside a string
        # value rather than as an actual LIMIT clause.
        query = "SELECT * FROM notes WHERE title = 'limit test'"
        result = ensure_limit(query, limit=50)
        assert result == "SELECT * FROM notes WHERE title = 'limit test' LIMIT 50"

    def test_not_fooled_by_limit_substring_in_column_name(self):
        query = "SELECT rate_limit_seconds FROM configs"
        result = ensure_limit(query, limit=50)
        assert result == "SELECT rate_limit_seconds FROM configs LIMIT 50"

    def test_default_limit_value_used_when_not_specified(self):
        result = ensure_limit("SELECT * FROM tracks")
        assert "LIMIT 100" in result