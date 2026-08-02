# HLS flow roles

## Orchestrator

Loads a testcase, runs the testbench, selects repair on failure or optimization on
success, and persists the JSON run report. It owns adapter invocation and status.

## Repair

Receives a failed validation and reads the two configured manifest fields: `what
problem occurred?` and `how should it be fixed?`. It returns structured guidance
only; it must not edit kernel or testbench code. It hands the guidance to the
orchestrator for the run report.

## Optimizer

Runs only after validation passes. It collects PPA and exposes strategy hooks, but
makes no source transformations. It hands PPA and its placeholder status back to
the orchestrator.
