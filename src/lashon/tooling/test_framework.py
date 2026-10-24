#!/usr/bin/env python3
"""
Testing framework for Lashon Studio

Provides automated testing capabilities for custom languages including:
- Unit test generation
- Test execution
- Coverage reporting
- Regression testing
"""

import io
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from lashon.config.language_config import LanguageConfig
from lashon.parser.parser_generator import ParserGenerator


@dataclass
class TestCase:
    """Represents a single test case."""

    __test__ = False  # Avoid pytest collecting utility container

    name: str
    code: str
    expected_output: Optional[str] = None
    expected_tokens: Optional[int] = None
    expected_ast_nodes: Optional[int] = None
    should_pass: bool = True
    description: str = ""
    test_type: str = "general"
    tags: List[str] = field(default_factory=list)


@dataclass
class TestResult:
    """Result of running a test case."""

    __test__ = False  # Avoid pytest collecting utility container

    test_name: str
    passed: bool
    message: str = ""
    execution_time: float = 0.0
    output: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def error_message(self) -> Optional[str]:
        """Backwards compatible alias used by older test helpers."""
        return self.error


class LanguageTestRunner:
    """Runs tests for custom languages."""

    def __init__(self, config: LanguageConfig):
        self.config = config
        self.parser_gen = ParserGenerator(config)
        self.test_cases: List[TestCase] = []
        self.results: List[TestResult] = []
        self.last_report: Optional[Dict[str, Any]] = None

    def add_test(self, test: TestCase) -> None:
        """Add a test case."""
        self.test_cases.append(test)

    def add_tests(self, tests: List[TestCase]) -> None:
        """Add multiple test cases."""
        self.test_cases.extend(tests)

    def run_all_tests(self, tests: Optional[List[TestCase]] = None) -> List[TestResult]:
        """Run test cases and return the collected results."""
        test_suite = tests if tests is not None else self.test_cases
        self.results = []
        start_time = datetime.now()

        for test in test_suite:
            result = self.run_test(test)
            self.results.append(result)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        self.last_report = self.generate_report(duration)
        return list(self.results)

    def run_test(self, test: TestCase) -> TestResult:
        """Run a single test case."""
        start_time = datetime.now()

        try:
            # Parse the code
            tokens, ast = self.parser_gen.parse(test.code)

            # Check token count if specified
            if test.expected_tokens is not None:
                actual_tokens = len([t for t in tokens if t.type.value != "EOF"])
                if actual_tokens != test.expected_tokens:
                    return TestResult(
                        test.name,
                        False,
                        f"Token count mismatch: expected {test.expected_tokens}, got {actual_tokens}",  # noqa: E501 pylint: disable=line-too-long
                        execution_time=(datetime.now() - start_time).total_seconds(),
                    )

            # Check AST node count if specified
            if test.expected_ast_nodes is not None:
                actual_nodes = self.count_ast_nodes(ast)
                if actual_nodes != test.expected_ast_nodes:
                    return TestResult(
                        test.name,
                        False,
                        f"AST node count mismatch: expected {test.expected_ast_nodes}, got {actual_nodes}",  # noqa: E501 pylint: disable=line-too-long
                        execution_time=(datetime.now() - start_time).total_seconds(),
                    )

            # Try to execute the code
            output = self.execute_code(test.code)

            # Check expected output if specified
            if test.expected_output is not None:
                if output.strip() != test.expected_output.strip():
                    return TestResult(
                        test.name,
                        False,
                        "Output mismatch",
                        execution_time=(datetime.now() - start_time).total_seconds(),
                        output=output,
                        metadata={
                            "expected": test.expected_output,
                            "actual": output,
                        },
                    )

            # Test passed
            return TestResult(
                test.name,
                True,
                "Test passed",
                execution_time=(datetime.now() - start_time).total_seconds(),
                output=output,
                metadata={
                    "tokens": len(tokens),
                    "ast_nodes": self.count_ast_nodes(ast),
                },
            )

        except Exception as e:  # noqa: BLE001  # pylint: disable=broad-except
            # Test failed with exception
            if test.should_pass:
                return TestResult(
                    test.name,
                    False,
                    f"Test failed with exception: {type(e).__name__}",
                    execution_time=(datetime.now() - start_time).total_seconds(),
                    error=str(e),
                    metadata={"traceback": traceback.format_exc()},
                )
            else:
                # Test was expected to fail
                return TestResult(
                    test.name,
                    True,
                    "Test correctly failed as expected",
                    execution_time=(datetime.now() - start_time).total_seconds(),
                )

    def execute_code(self, code: str) -> str:
        """Execute code and capture output."""
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        redirected_output = io.StringIO()
        redirected_error = io.StringIO()

        try:
            sys.stdout = redirected_output
            sys.stderr = redirected_error

            # Execute in isolated namespace
            namespace = {"__name__": "__main__"}
            exec(code, namespace)  # noqa: S102  # pylint: disable=exec-used

            output = redirected_output.getvalue()
            errors = redirected_error.getvalue()

            return output + errors

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    def count_ast_nodes(self, node) -> int:
        """Recursively count AST nodes."""
        count = 1
        for child in node.children:
            count += self.count_ast_nodes(child)
        return count

    def generate_report(self, duration: float) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed
        pass_rate = (passed / len(self.results) * 100) if self.results else 0

        return {
            "summary": {
                "total": len(self.results),
                "passed": passed,
                "failed": failed,
                "pass_rate": f"{pass_rate:.1f}%",
                "duration": f"{duration:.3f}s",
            },
            "results": self.results,
            "config_name": self.config.name,
            "timestamp": datetime.now().isoformat(),
        }

    def print_report(self, report: Dict[str, Any]) -> str:
        """Format test report as string."""
        lines = []
        lines.append("=" * 70)
        lines.append(f"TEST REPORT: {self.config.name}")
        lines.append("=" * 70)
        lines.append("")

        summary = report["summary"]
        lines.append(f"Total Tests:  {summary['total']}")
        lines.append(f"Passed:       {summary['passed']} ✓")
        lines.append(f"Failed:       {summary['failed']} ✗")
        lines.append(f"Pass Rate:    {summary['pass_rate']}")
        lines.append(f"Duration:     {summary['duration']}")
        lines.append("")
        lines.append("=" * 70)
        lines.append("DETAILED RESULTS")
        lines.append("=" * 70)
        lines.append("")

        for result in self.results:
            status = "✓ PASS" if result.passed else "✗ FAIL"
            lines.append(
                f"{status} | {result.test_name} ({result.execution_time:.3f}s)"
            )
            if not result.passed:
                lines.append(f"       {result.message}")
                if result.error:
                    lines.append(f"       Error: {result.error}")
            lines.append("")

        lines.append("=" * 70)
        return "\n".join(lines)


class TestGenerator:
    """Generates test cases for language configurations."""

    __test__ = False  # Avoid pytest collecting utility helper

    def __init__(self, config: LanguageConfig):
        self.config = config

    def generate_basic_tests(self) -> List[TestCase]:
        """Generate basic test cases for the language."""
        tests = []

        # Test 1: Basic keyword recognition
        keywords_sample = " ".join(
            [kw.custom for kw in list(self.config.keyword_mappings.values())[:3]]
        )
        tests.append(
            TestCase(
                name="keyword_recognition",
                code=keywords_sample,
                description="Test that custom keywords are recognized",
                tags=["keywords", "basic"],
            )
        )

        # Test 2: Number parsing
        tests.append(
            TestCase(
                name="number_parsing",
                code="42 3.14 0.5",
                expected_tokens=3,
                description="Test number tokenization",
                tags=["numbers", "basic"],
            )
        )

        # Test 3: String parsing
        tests.append(
            TestCase(
                name="string_parsing",
                code="\"hello\" 'world'",
                expected_tokens=2,
                description="Test string tokenization",
                tags=["strings", "basic"],
            )
        )

        # Test 4: Comment handling
        comment_style = self.config.syntax_options.single_line_comment
        if comment_style:
            tests.append(
                TestCase(
                    name="comment_handling",
                    code=f"{comment_style} This is a comment\n42",
                    description="Test comment recognition",
                    tags=["comments", "basic"],
                )
            )

        # Test 5: Function name recognition
        if self.config.builtin_functions:
            func_name = list(self.config.builtin_functions.values())[0].name
            tests.append(
                TestCase(
                    name="function_recognition",
                    code=f"{func_name}()",
                    description="Test function recognition",
                    tags=["functions", "basic"],
                )
            )

        return tests

    def generate_stress_tests(self) -> List[TestCase]:
        """Generate stress tests."""
        tests = []

        # Large file test
        tests.append(
            TestCase(
                name="large_file_parsing",
                code="\n".join([f"x{i} = {i}" for i in range(100)]),
                description="Test parsing large file",
                tags=["stress", "performance"],
            )
        )

        # Deep nesting test
        tests.append(
            TestCase(
                name="deep_nesting",
                code="(" * 50 + "42" + ")" * 50,
                description="Test deeply nested expressions",
                tags=["stress", "nesting"],
            )
        )

        return tests

    def generate_error_tests(self) -> List[TestCase]:
        """Generate tests that should fail."""
        tests = []

        # Unclosed string
        tests.append(
            TestCase(
                name="unclosed_string_error",
                code='"unclosed string',
                should_pass=False,
                description="Test handling of unclosed string",
                tags=["errors", "strings"],
            )
        )

        # Invalid syntax
        tests.append(
            TestCase(
                name="invalid_syntax_error",
                code="def def def",
                should_pass=False,
                description="Test handling of invalid syntax",
                tags=["errors", "syntax"],
            )
        )

        return tests


class CoverageAnalyzer:
    """Analyzes test coverage for language features."""

    def __init__(self, config: LanguageConfig):
        self.config = config

    def analyze_coverage(self, test_cases: List[TestCase]) -> Dict[str, Any]:
        """Analyze what language features are covered by tests."""
        coverage = {
            "keywords": self.analyze_keyword_coverage(test_cases),
            "functions": self.analyze_function_coverage(test_cases),
            "syntax": self.analyze_syntax_coverage(test_cases),
        }

        return coverage

    def analyze_keyword_coverage(self, test_cases: List[TestCase]) -> Dict[str, Any]:
        """Check which keywords are tested."""
        all_keywords = set(kw.custom for kw in self.config.keyword_mappings.values())
        tested_keywords = set()

        for test in test_cases:
            for keyword in all_keywords:
                if keyword in test.code:
                    tested_keywords.add(keyword)

        coverage_pct = (
            len(tested_keywords) / len(all_keywords) * 100 if all_keywords else 0
        )

        return {
            "total": len(all_keywords),
            "tested": len(tested_keywords),
            "coverage": f"{coverage_pct:.1f}%",
            "untested": list(all_keywords - tested_keywords),
        }

    def analyze_function_coverage(self, test_cases: List[TestCase]) -> Dict[str, Any]:
        """Check which functions are tested."""
        all_functions = set(f.name for f in self.config.builtin_functions.values())
        tested_functions = set()

        for test in test_cases:
            for func in all_functions:
                if func in test.code:
                    tested_functions.add(func)

        coverage_pct = (
            len(tested_functions) / len(all_functions) * 100 if all_functions else 0
        )

        return {
            "total": len(all_functions),
            "tested": len(tested_functions),
            "coverage": f"{coverage_pct:.1f}%",
            "untested": list(all_functions - tested_functions),
        }

    def analyze_syntax_coverage(self, test_cases: List[TestCase]) -> Dict[str, str]:
        """Check which syntax features are tested."""
        features_tested = {
            "strings": any('"' in t.code or "'" in t.code for t in test_cases),
            "numbers": any(c.isdigit() for t in test_cases for c in t.code),
            "comments": any(
                self.config.syntax_options.single_line_comment in t.code
                for t in test_cases
            ),
        }

        return {k: "✓" if v else "✗" for k, v in features_tested.items()}


def create_test_suite(
    config: LanguageConfig,
    include_stress: bool = False,
    include_errors: bool = True,
) -> LanguageTestRunner:
    """Create a complete test suite for a language configuration."""
    runner = LanguageTestRunner(config)
    generator = TestGenerator(config)

    # Add basic tests
    runner.add_tests(generator.generate_basic_tests())

    # Add stress tests if requested
    if include_stress:
        runner.add_tests(generator.generate_stress_tests())

    # Add error tests if requested
    if include_errors:
        runner.add_tests(generator.generate_error_tests())

    return runner
