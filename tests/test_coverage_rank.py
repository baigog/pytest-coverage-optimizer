import json
import subprocess
import sys
from pathlib import Path


def run_script(script, *args):
    cmd = [sys.executable, str(script)] + list(args)
    return subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )


def write_coverage(tmp_path, files):
    path = tmp_path / "coverage.json"
    path.write_text(json.dumps({"files": files, "totals": {}}), encoding="utf-8")
    return path


def rank(tmp_path, coverage, *extra):
    output = tmp_path / "ranking.json"
    script = Path(__file__).parents[1] / "scripts" / "coverage_rank.py"
    run_script(
        script,
        "--coverage",
        str(coverage),
        "--root",
        str(tmp_path),
        "--output",
        str(output),
        *extra
    )
    return json.loads(output.read_text(encoding="utf-8"))


def test_ranker_avoids_module_and_class_duplication(tmp_path):
    src = tmp_path / "mod.py"
    src.write_text(
        "x = 1\n"
        "\n"
        "class Demo:\n"
        "    y = 2\n"
        "\n"
        "    def method(self, value):\n"
        "        if value:\n"
        "            return 1\n"
        "        return 0\n",
        encoding="utf-8",
    )
    coverage = write_coverage(
        tmp_path,
        {
            "mod.py": {
                "executed_lines": [1, 3, 6, 7, 8],
                "missing_lines": [4, 9],
                "missing_branches": [[7, 9]],
            }
        },
    )

    data = rank(tmp_path, coverage)
    by_symbol = {item["symbol"]: item for item in data["targets"]}

    assert "<module>" not in by_symbol
    assert by_symbol["Demo"]["missing_lines"] == [4]
    assert by_symbol["Demo.method"]["missing_lines"] == [9]
    assert by_symbol["Demo.method"]["missing_branches"] == [[7, 9]]


def test_qualified_dependency_detection_and_owned_class_scope(tmp_path):
    src = tmp_path / "service.py"
    src.write_text(
        "import requests as client\n"
        "\n"
        "class Service:\n"
        "    marker = 1\n"
        "\n"
        "    def fetch(self):\n"
        "        return client.get('https://example.invalid')\n",
        encoding="utf-8",
    )
    coverage = write_coverage(
        tmp_path,
        {
            "service.py": {
                "executed_lines": [1, 3, 6],
                "missing_lines": [4, 7],
                "missing_branches": [],
            }
        },
    )

    data = rank(tmp_path, coverage)
    by_symbol = {item["symbol"]: item for item in data["targets"]}

    assert by_symbol["Service"]["setup_tier"] == 0
    assert by_symbol["Service"]["complexity_estimate"] == 1
    assert by_symbol["Service.fetch"]["setup_tier"] == 3
    assert "EXTERNAL:requests.get" in by_symbol["Service.fetch"]["boundary_flags"]


def test_existing_tests_create_clear_selection_classes(tmp_path):
    src_dir = tmp_path / "src" / "pkg"
    tests_dir = tmp_path / "tests"
    src_dir.mkdir(parents=True)
    tests_dir.mkdir()
    source = src_dir / "calc.py"
    source.write_text(
        "def covered_nearby(value):\n"
        "    if value:\n"
        "        return 1\n"
        "    return 0\n"
        "\n"
        "def no_test(value):\n"
        "    if value:\n"
        "        return 2\n"
        "    return 0\n",
        encoding="utf-8",
    )
    (tests_dir / "test_calc.py").write_text(
        "from pkg.calc import covered_nearby\n\n"
        "def test_existing():\n"
        "    assert covered_nearby(True) == 1\n",
        encoding="utf-8",
    )
    coverage = write_coverage(
        tmp_path,
        {
            "src/pkg/calc.py": {
                "executed_lines": [1, 2, 3, 6, 7, 8],
                "missing_lines": [4, 9],
                "missing_branches": [[2, 4], [7, 9]],
            }
        },
    )

    data = rank(tmp_path, coverage)
    by_symbol = {item["symbol"]: item for item in data["targets"]}

    assert by_symbol["covered_nearby"]["selection_class"] == "A"
    assert by_symbol["covered_nearby"]["agent_action"] == "ATTEMPT"
    # Module evidence is deliberately shared for the same source file.
    assert by_symbol["no_test"]["selection_class"] == "A"
    assert by_symbol["no_test"]["test_evidence"]["paths"] == ["tests/test_calc.py"]


def test_history_skips_stable_rejection_and_promotes_shared_setup(tmp_path):
    src = tmp_path / "mod.py"
    tests = tmp_path / "tests"
    tests.mkdir()
    src.write_text(
        "def first(value):\n"
        "    if value:\n"
        "        return 1\n"
        "    return 0\n"
        "\n"
        "def second(value):\n"
        "    if value:\n"
        "        return 2\n"
        "    return 0\n",
        encoding="utf-8",
    )
    coverage = write_coverage(
        tmp_path,
        {
            "mod.py": {
                "executed_lines": [1, 2, 3, 6, 7, 8],
                "missing_lines": [4, 9],
                "missing_branches": [[2, 4], [7, 9]],
            }
        },
    )
    history = tmp_path / "iterations.jsonl"
    history.write_text(
        json.dumps({"target": "mod.py::first", "status": "accepted"}) + "\n" +
        json.dumps({
            "target": "mod.py::second",
            "status": "rejected",
            "reason_code": "UNREACHABLE",
        }) + "\n",
        encoding="utf-8",
    )

    data = rank(tmp_path, coverage, "--history", str(history), "--include-skipped")
    by_symbol = {item["symbol"]: item for item in data["targets"]}

    assert by_symbol["first"]["history"]["shared_setup"] is True
    assert by_symbol["first"]["selection_class"] == "B"
    assert by_symbol["second"]["selection_class"] == "Z"
    assert by_symbol["second"]["agent_action"] == "SKIP"


def test_two_no_gain_attempts_demote_candidate(tmp_path):
    src = tmp_path / "mod.py"
    src.write_text(
        "def target(value):\n"
        "    if value:\n"
        "        return 1\n"
        "    return 0\n",
        encoding="utf-8",
    )
    coverage = write_coverage(
        tmp_path,
        {
            "mod.py": {
                "executed_lines": [1, 2, 3],
                "missing_lines": [4],
                "missing_branches": [[2, 4]],
            }
        },
    )
    history = tmp_path / "iterations.jsonl"
    history.write_text(
        json.dumps({"target": "mod.py::target", "status": "no_gain"}) + "\n" +
        json.dumps({"target": "mod.py::target", "status": "failed"}) + "\n",
        encoding="utf-8",
    )

    data = rank(tmp_path, coverage, "--history", str(history))
    item = data["targets"][0]

    assert item["selection_class"] == "D"
    assert item["history"]["no_gain_attempts"] == 2


def test_query_coverage_returns_requested_slice(tmp_path):
    coverage = {
        "files": {
            "src/pkg/mod.py": {
                "executed_lines": [1, 2, 10],
                "missing_lines": [3, 11],
                "executed_branches": [[2, 3]],
                "missing_branches": [[10, 11]],
                "contexts": {"2": ["test_a"], "10": ["test_b"]},
            }
        }
    }
    cov_path = tmp_path / "coverage.json"
    cov_path.write_text(json.dumps(coverage), encoding="utf-8")
    script = Path(__file__).parents[1] / "scripts" / "query_coverage.py"

    result = run_script(
        script,
        "--coverage",
        str(cov_path),
        "--file",
        "src/pkg/mod.py",
        "--start",
        "1",
        "--end",
        "5",
    )
    data = json.loads(result.stdout)

    assert data["executed_lines"] == [1, 2]
    assert data["missing_lines"] == [3]
    assert data["executed_branches"] == [[2, 3]]
    assert data["missing_branches"] == []
    assert data["contexts"] == {"2": ["test_a"]}


def test_scripts_compile_on_current_interpreter():
    root = Path(__file__).parents[1]
    for path in [
        root / "scripts" / "coverage_rank.py",
        root / "scripts" / "ranking_ast.py",
        root / "scripts" / "ranking_context.py",
        root / "scripts" / "query_coverage.py",
    ]:
        source = path.read_text(encoding="utf-8")
        compile(source, str(path), "exec")


def test_scripts_parse_with_python_37_grammar():
    import ast

    root = Path(__file__).parents[1]
    for path in [
        root / "scripts" / "coverage_rank.py",
        root / "scripts" / "ranking_ast.py",
        root / "scripts" / "ranking_context.py",
        root / "scripts" / "query_coverage.py",
    ]:
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path), feature_version=(3, 7))


def test_class_order_is_not_overridden_by_larger_raw_gain(tmp_path):
    src_dir = tmp_path / "src" / "pkg"
    tests_dir = tmp_path / "tests"
    src_dir.mkdir(parents=True)
    tests_dir.mkdir()
    source = src_dir / "targets.py"
    source.write_text(
        "def nearby(value):\n"
        "    if value:\n"
        "        return 1\n"
        "    return 0\n"
        "\n"
        "def expensive_without_tests(a, b, c):\n"
        "    if a:\n"
        "        x = 1\n"
        "    else:\n"
        "        x = 2\n"
        "    if b:\n"
        "        x += 3\n"
        "    else:\n"
        "        x += 4\n"
        "    if c:\n"
        "        x += 5\n"
        "    return x\n",
        encoding="utf-8",
    )
    (tests_dir / "test_nearby.py").write_text(
        "from pkg.targets import nearby\n\n"
        "def test_nearby():\n"
        "    assert nearby(True) == 1\n",
        encoding="utf-8",
    )
    coverage = write_coverage(
        tmp_path,
        {
            "src/pkg/targets.py": {
                "executed_lines": [1, 2, 3, 6, 7],
                "missing_lines": [4, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17],
                "missing_branches": [[2, 4], [7, 8], [7, 10], [11, 12], [11, 14], [15, 16]],
            }
        },
    )

    data = rank(tmp_path, coverage)

    assert data["targets"][0]["symbol"] == "nearby"
    assert data["targets"][0]["selection_class"] == "A"
