"""Helpers for locating, loading, and running benchmark testcases."""

from dataclasses import dataclass
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

@dataclass(frozen=True)
class ProcessResult:
    """The outcome of one external process invoked by the testcase runner."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        """Whether the testcase compiled and its testbench passed."""
        return self.exit_code == 0

    @property
    def error(self) -> str:
        """Return the failure reported by the compiler or testbench."""
        if self.passed:
            return ""
        return self.stderr or self.stdout or "Process failed without output"



def _load_benchmark(benchmark_name: str) -> Path:
    """Return the directory for *benchmark_name*.

    Benchmark names are resolved below the repository's ``benchmarks`` directory
    so the CLI accepts names such as ``vector_add`` rather than filesystem paths.
    """
    if not benchmark_name or Path(benchmark_name).name != benchmark_name:
        raise ValueError("benchmark name must be a single directory name")

    benchmarks_root = Path(__file__).resolve().parent.parent / "benchmarks"
    testcase = benchmarks_root / benchmark_name
    if not testcase.is_dir():
        raise FileNotFoundError(f"benchmark '{benchmark_name}' was not found at {testcase}")

    return testcase


def list_testcases(benchmark_name: str) -> list[Path]:
    """Return the benchmark's testcase files in stable numbered order."""
    benchmark = _load_benchmark(benchmark_name)
    testcases = sorted((benchmark / "test_cases").glob("*.cpp"))
    if not testcases:
        raise FileNotFoundError(f"benchmark '{benchmark_name}' has no testcase files")
    return testcases


def load_testcase(benchmark_name: str, testcase_number: int) -> Path:
    """Load one testcase using its one-based number in the benchmark list."""
    testcases = list_testcases(benchmark_name)
    if not 1 <= testcase_number <= len(testcases):
        raise ValueError(
            f"testcase number must be between 1 and {len(testcases)} for "
            f"benchmark '{benchmark_name}'"
        )
    return testcases[testcase_number - 1]


def compile_testcase(
    benchmark_name: str, testcase_number: int, testcase_file: Path | None = None
) -> ProcessResult:
    """Run C simulation for a selected testcase through Vitis HLS.

    Vitis receives the benchmark-local ``task.cfg`` and writes all generated
    output into ``working_directory``.  Loading the testcase here preserves the
    runner's validation of the selected one-based testcase number; source files
    and testbench settings are supplied by the benchmark's configuration file.
    """
    benchmark = _load_benchmark(benchmark_name)
    selected_testcase = load_testcase(benchmark_name, testcase_number)
    testcase = (testcase_file or selected_testcase).resolve()
    if not testcase.is_file():
        raise FileNotFoundError(f"testcase file was not found at {testcase}")
    template_path = benchmark / "task.cfg"
    if not template_path.is_file():
        raise FileNotFoundError(
            f"benchmark '{benchmark_name}' has no Vitis configuration at {template_path}"
        )

    config = template_path.read_text(encoding="utf-8")
    config = config.replace("{TEST_CASE_FILE}", str(testcase.resolve()))
    config = config.replace("{TEST_CASE_FUNCTION}", benchmark_name)
    config = config.replace("{TEST_BENCH_FILE}", str(benchmark.resolve() / f"{benchmark_name}_test.cpp"))

    with TemporaryDirectory(prefix="vitis_hls_") as temp_dir:
        config_path = Path(temp_dir) / "task.cfg"
        config_path.write_text(config, encoding="utf-8")


        compilation = subprocess.run(
            [
                "vitis-run",
                "--mode",
                "hls",
                "--csim",
                "--config",
                str(config_path),
                "--work_dir",
                str(Path(__file__).resolve().parent.parent),
            ],
            capture_output=True,
            text=True,
        )
    return ProcessResult(
        exit_code=compilation.returncode,
        stdout=compilation.stdout,
        stderr=compilation.stderr,
    )


def run_testcase(
    benchmark_name: str, testcase_number: int, testcase_file: Path | None = None
) -> ProcessResult:
    """Run a testcase, optionally substituting a repaired source file."""
    return compile_testcase(benchmark_name, testcase_number, testcase_file)
