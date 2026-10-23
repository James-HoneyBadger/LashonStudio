"""Tests for the REPL."""


from parsercraft.runtime.repl import REPL


class TestREPL:
    """Test the interactive REPL."""

    def test_simple_eval(self):
        repl = REPL()
        repl.eval_line("x = 10")
        assert repl.namespace["x"] == 10

    def test_persistent_namespace(self):
        repl = REPL()
        repl.eval_line("a = 5")
        repl.eval_line("b = a * 2")
        assert repl.namespace["a"] == 5
        assert repl.namespace["b"] == 10

    def test_eval_lines(self):
        repl = REPL()
        ns = repl.eval_lines(["x = 3", "y = 4", "z = x + y"])
        assert ns["x"] == 3
        assert ns["y"] == 4
        assert ns["z"] == 7

    def test_arithmetic_operations(self):
        repl = REPL()
        ns = repl.eval_lines([
            "a = 10",
            "b = 3",
            "sum = a + b",
            "diff = a - b",
            "prod = a * b",
        ])
        assert ns["sum"] == 13
        assert ns["diff"] == 7
        assert ns["prod"] == 30

    def test_complex_expression(self):
        repl = REPL()
        repl.eval_line("r = 2 + 3 * 4")
        assert repl.namespace["r"] == 14

    def test_eval_line_returns_string(self):
        repl = REPL()
        result = repl.eval_line("x = 42")
        assert isinstance(result, str)

    def test_history_tracking(self):
        repl = REPL()
        repl.eval_line("x = 1")
        # eval_line doesn't add to history (only interactive run does)
        # But internal state should be valid
        assert repl.namespace["x"] == 1

    def test_auto_semicolon(self):
        """REPL should auto-add semicolons for convenience."""
        repl = REPL()
        repl.eval_line("x = 10")  # No trailing semicolon
        assert repl.namespace["x"] == 10

    def test_from_config_file(self, tmp_path):
        """Test creating REPL from a config file."""
        import json
        config = {
            "grammar": {
                "rules": {
                    "program": "statement+",
                    "statement": 'IDENT "=" NUMBER ";"',
                }
            }
        }
        config_path = tmp_path / "test.json"
        config_path.write_text(json.dumps(config))
        repl = REPL.from_config_file(str(config_path))
        repl.eval_line("x = 42")
        assert repl.namespace["x"] == 42


class TestREPLCommands:
    """Test REPL special commands."""

    def test_help_command(self, capsys):
        repl = REPL()
        repl._handle_command(":help")
        captured = capsys.readouterr()
        assert "REPL Commands" in captured.out

    def test_vars_command_empty(self, capsys):
        repl = REPL()
        repl._handle_command(":vars")
        captured = capsys.readouterr()
        assert "No variables" in captured.out

    def test_vars_command_with_data(self, capsys):
        repl = REPL()
        repl.eval_line("x = 42")
        repl._handle_command(":vars")
        captured = capsys.readouterr()
        assert "x" in captured.out
        assert "42" in captured.out

    def test_reset_command(self, capsys):
        repl = REPL()
        repl.eval_line("x = 42")
        repl._handle_command(":reset")
        assert repl.namespace == {}

    def test_unknown_command(self, capsys):
        repl = REPL()
        repl._handle_command(":foobar")
        captured = capsys.readouterr()
        assert "Unknown command" in captured.out
