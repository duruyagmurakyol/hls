"""CLI entry point for selecting and running an HLS benchmark testcase."""

import argparse
import sys

from repair import run_repair
from testcase_runner import ProcessResult, list_testcases, load_testcase, run_testcase

MAX_REPAIR_ATTEMPTS = 1

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select and run an HLS benchmark testcase.")
    parser.add_argument("benchmark", help="benchmark name under benchmarks/")
    return parser.parse_args()


def main() -> int:
    """Prompt for, load, and run a testcase from the selected benchmark."""
    args = parse_args()
    try:
        available_testcases = list_testcases(args.benchmark)
        print(f"Testcases for {args.benchmark}:")
        for number, testcase in enumerate(available_testcases, start=1):
            print(f"  {number}. {testcase.name}")

        testcase_number = int(input("Testcase number: "))
        testcase = load_testcase(args.benchmark, testcase_number)
        print(f"Running {testcase}", flush=True)
    except (ValueError, FileNotFoundError) as error:
        raise SystemExit(f"error: {error}") from error

    result = ProcessResult( exit_code=1,stdout="",stderr="") #run_testcase(args.benchmark, testcase_number)
    repair_attempts = 0
    while not result.passed and repair_attempts < MAX_REPAIR_ATTEMPTS:
        print(
            f"Testcase failed with exit code {result.exit_code}.",
            file=sys.stderr,
        )
        run_repair(testcase, result)
        print(f" Repair completed.", file=sys.stderr)

        repair_attempts += 1
        print("Re-running testcase after repair.", file=sys.stderr)
        result = run_testcase(args.benchmark, testcase_number)

    if result.passed:
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        print("ready for optimisation")
        return 0

    print(
        f"Testcase failed with exit code {result.exit_code}.",
        file=sys.stderr,
    )
    print(f"Stopping after {MAX_REPAIR_ATTEMPTS} retries.", file=sys.stderr)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
