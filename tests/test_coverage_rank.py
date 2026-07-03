import json
import subprocess
import sys
from pathlib import Path


def run_script(script, *args):
    cmd = [sys.executable, str(script)] + list(args)
    return subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)


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
    coverage = {
        "files": {
            "mod.py": {
                "executed_lines": [1, 3, 6, 7, 8],
                "missing_lines": [4, 9],
                "missing_branches": [[7, 9]],
            }
        },
        "totals": {},
    }
    cov_path = tmp_path / "coverage.json"
    cov_path.write_text(json.dumps(coverage), encoding="utf-8")
    out_path = tmp_path / "ranking.json"
    script = Path(__file__).parents[1] / "scripts" / "coverage_rank.py"

    run_script(
        script,
        "--coverage", str(cov_path),
        "--root", str(tmp_path),
        "--output", str(out_path),
    )

    data = json.loads(out_path.read_text(encoding="utf-8"))
    by_symbol = {item["symbol"]: item for item in data["targets"]}

    assert "<module>" not in by_symbol
    assert by_symbol["Demo"]["missing_lines"] == [4]
    assert by_symbol["Demo.method"]["missing_lines"] == [9]
    assert by_symbol["Demo.method"]["missing_branches"] == [[7, 9]]


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
        "--coverage", str(cov_path),
        "--file", "src/pkg/mod.py",
        "--start", "1",
        "--end", "5",
    )
    data = json.loads(result.stdout)

    assert data["executed_lines"] == [1, 2]
    assert data["missing_lines"] == [3]
    assert data["executed_branches"] == [[2, 3]]
    assert data["missing_branches"] == []
    assert data["contexts"] == {"2": ["test_a"]}


def test_scripts_compile_on_current_interpreter():
    root = Path(__file__).parents[1]
    for path in [root / "scripts" / "coverage_rank.py", root / "scripts" / "query_coverage.py"]:
        source = path.read_text(encoding="utf-8")
        compile(source, str(path), "exec")
