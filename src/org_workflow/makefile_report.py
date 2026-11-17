"""Run a make target prerequisite by prerequisite and report on each described target. Write a tab-separated line
per described target to standard output, giving the name, description, outcome and detail. The outcome
is passed, failed, warning, or not run when a prerequisite failed. The detail is the text printed by the recipe on
lines starting "report:". A report line holding a tab gives the label and outcome of a check within the target, on a
separate line with an empty target. The failure of a target with a description starting "Warning:" counts as a
warning and does not stop the dependent targets. Write the make output to standard error and pass further arguments
to make. Exit with failure if any target failed. With --check in place of a target, check that each workflow
reporting on a target is named by the description of that target."""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys
from functools import cache

from org_workflow.makefile import Rule, makefile_rules

REPORT = re.compile(r"makefile-report\s+([\w.-]+)")
NAME = re.compile(r"^name:\s*(.+)$", re.MULTILINE)


def reporting_workflows() -> list[tuple[pathlib.Path, str, str]]:
    """File, name and reported target of each workflow running this script on a target"""
    result = []
    for workflow in sorted(pathlib.Path(".github/workflows").glob("*.yml")):
        text = workflow.read_text()
        if (run := REPORT.search(text)) and (name := NAME.search(text)):
            result.append((workflow, name[1].strip(), run[1]))
    return result


def check_workflows(graph: dict[str, Rule]) -> None:
    misnamed = [
        f"{workflow}: named {name!r}, not {graph[target].description!r}"
        for workflow, name, target in reporting_workflows()
        if target not in graph or name != graph[target].description
    ]
    for line in misnamed:
        print(line)
    sys.exit(bool(misnamed))


def main() -> None:
    root, *options = sys.argv[1:]
    graph = makefile_rules()
    if root == "--check":
        check_workflows(graph)
    report: list[str] = []
    warnings = [t for t, rule in graph.items() if rule.warning]

    @cache
    def run(target: str) -> str:
        """Run a target after its prerequisites and report the outcome if the target is described"""
        if target not in graph:
            return "passed"
        rule = graph[target]
        assert rule.description or not rule.recipe or target.startswith("."), (
            f"{target} is not described"
        )
        details: list[str] = []
        checks: list[str] = []
        if any(
            outcome not in ("passed", "warning") for outcome in [run(p) for p in rule.prerequisites]
        ):
            outcome = "not run"
        else:
            made = subprocess.run(
                ["make", target, *[f"--old-file={w}" for w in warnings if w != target], *options],
                capture_output=True,
                text=True,
                errors="replace",
                check=False,
                env={**os.environ, "REPORT": "1"},
            )
            sys.stderr.write(made.stdout + made.stderr)
            outcome = "passed" if made.returncode == 0 else "warning" if rule.warning else "failed"
            lines = [
                line.removeprefix("report: ")
                for line in made.stdout.splitlines()
                if line.startswith("report: ")
            ]
            details = [line for line in lines if "\t" not in line]
            checks = [line for line in lines if "\t" in line]
            if outcome != "passed" and not details:
                output = [
                    line
                    for line in made.stderr.splitlines()
                    if line and not line.startswith("make")
                ]
                details = output[-1:]
        if rule.description:
            report.append(f"{target}\t{rule.description}\t{outcome}\t{'; '.join(details)}")
            report.extend(f"\t{check}\t" for check in checks)
        return outcome

    outcome = run(root)
    sys.stdout.write("".join(line + "\n" for line in report))
    sys.exit(outcome not in ("passed", "warning"))
