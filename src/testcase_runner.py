"""Helpers for locating, loading, and running benchmark testcases."""

from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile


@dataclass(frozen=True)
class ProcessResult:
    """The outcome of one external process invoked by the testcase runner."""

    exit_code: int
    stdout: str
    stderr: str
    stage: str

    @property
    def passed(self) -> bool:
        """Whether the testcase compiled and its testbench passed."""
        return self.exit_code == 0

    @property
    def error(self) -> str:
        """Return the failure reported by the compiler or testbench."""
        if self.passed:
            return ""
        return self.stderr or self.stdout or f"{self.stage} failed without output"


@dataclass(frozen=True)
class CompilationResult(ProcessResult):
    """The outcome of running Vitis HLS C simulation for a testcase."""

    working_directory: Path


@dataclass(frozen=True)
class ExecutionResult(ProcessResult):
    """The outcome of running a compiled testcase executable."""


@dataclass(frozen=True)
class TestcaseResult:
    """The outcome of validating one testcase with Vitis HLS."""

    compilation: CompilationResult
    execution: ExecutionResult | None

    @property
    def passed(self) -> bool:
        """Whether the Vitis HLS C-simulation flow passed."""
        return self.compilation.passed

    @property
    def exit_code(self) -> int:
        """Return the exit code from the failing stage, or zero on success."""
        if not self.compilation.passed:
            return self.compilation.exit_code
        return self.execution.exit_code if self.execution is not None else 0

    @property
    def stage(self) -> str:
        """Return the stage that determined this result."""
        if not self.compilation.passed:
            return self.compilation.stage
        return self.execution.stage if self.execution is not None else self.compilation.stage

    @property
    def stdout(self) -> str:
        """Return output from the stage that determined this result."""
        if not self.compilation.passed:
            return self.compilation.stdout
        return self.execution.stdout if self.execution is not None else self.compilation.stdout

    @property
    def stderr(self) -> str:
        """Return diagnostics from the stage that determined this result."""
        if not self.compilation.passed:
            return self.compilation.stderr
        return self.execution.stderr if self.execution is not None else self.compilation.stderr

    @property
    def error(self) -> str:
        """Return the compiler or testbench failure message."""
        if self.passed:
            return ""
        return self.stderr or self.stdout or f"{self.stage} failed without output"


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
    benchmark_name: str, testcase_number: int, working_directory: Path
) -> CompilationResult:
    """Run C simulation for a selected testcase through Vitis HLS.

    Vitis receives the benchmark-local ``task.cfg`` and writes all generated
    output into ``working_directory``.  Loading the testcase here preserves the
    runner's validation of the selected one-based testcase number; source files
    and testbench settings are supplied by the benchmark's configuration file.
    """
    benchmark = _load_benchmark(benchmark_name)
    load_testcase(benchmark_name, testcase_number)
    config_path = benchmark / "task.cfg"
    if not config_path.is_file():
        raise FileNotFoundError(
            f"benchmark '{benchmark_name}' has no Vitis configuration at {config_path}"
        )

    compilation = subprocess.run(
        [
            "vitis-run",
            "--mode",
            "hls",
            "--csim",
            "--config",
            str(config_path),
            "--work_dir",
            str(working_directory),
        ],
        capture_output=True,
        text=True,
    )
    return CompilationResult(
        exit_code=compilation.returncode,
        stdout=compilation.stdout,
        stderr=compilation.stderr,
        stage="Vitis HLS C simulation",
        working_directory=working_directory,
    )


def run_testcase(benchmark_name: str, testcase_number: int) -> TestcaseResult:
    """Run a selected testcase in a temporary Vitis HLS working directory."""
    with tempfile.TemporaryDirectory(prefix=f"hls-{benchmark_name}-") as build_dir:
        compilation = compile_testcase(
            benchmark_name, testcase_number, Path(build_dir)
        )
        return TestcaseResult(compilation=compilation, execution=None)
