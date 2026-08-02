from pathlib import Path
from testcase_runner import ProcessResult
from siliconflow import complete

def failure_class(output: str) -> str:
    """Map host-validation text to the coarse category included in the prompt."""

    lower = output.lower()
    if "undefined reference" in lower or "linker" in lower:
        return "interface_or_link"
    if "error:" in lower or "expected" in lower and "before" in lower:
        return "compile"
    if "fail index=" in lower or "expected=" in lower and "actual=" in lower:
        return "functional"
    return "unknown"

def concise_evidence(output: str, limit: int = 1200) -> str:
    """Keep the last relevant diagnostic lines, capped for a compact API prompt."""

    lines = [line for line in output.splitlines() if line.strip()]
    selected = [
        line
        for line in lines
        if any(
            token in line.lower()
            for token in ("error", "undefined", "fail", "expected", "actual")
        )
    ]
    text = "\n".join(selected[-12:] or lines[-12:])
    return text[-limit:]


def run_repair(testcase: Path, result: ProcessResult) -> bool:
    """"""
    system = (
            "You repair AMD/Xilinx HLS C++ code. Return only the complete repaired contents "
            "of the editable source file. Do not use Markdown fences, explanations, JSON, or patches. "
            "Preserve the declared top-function interface and make the smallest necessary repair."
        )

    testcase = testcase.resolve()
    source = testcase.read_text(encoding="utf-8")
    benchmark = testcase.parent.parent
    contexts: list[str] = []
    for name in [benchmark / f"{benchmark.name}_test.cpp", benchmark / "task.cfg"]:
        contexts.append(
            f"FILE: {name}\n```\n{Path(name).read_text(encoding='utf-8')}\n```"
        )

    user = (
            f"Failure class: {failure_class(result.error)}\n"
            f"Failure evidence:\n{concise_evidence(result.error)}\n\n"
            f"```\n{source}\n```\n\n"
            + "\n\n".join(contexts)
            + "\n\nReturn only the full repaired editable file."
        )


    temperature=0
    max_output_tokens=2048
    api_timeout_seconds=120
    model="Qwen/Qwen3.5-122B-A10B"

    response = complete(
            model=model,
            system_prompt=system,
            user_prompt=user,
            temperature=temperature,
            max_tokens=max_output_tokens,
            timeout_seconds=api_timeout_seconds,
            thinking_budget=None # maybe change?
        )
    
    
    print(f"Model response:\n{response}")
    return False
