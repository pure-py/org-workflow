"""Rules and target descriptions of a Makefile"""

from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass

RULE = re.compile(r"^(?P<target>[^\s:#=$%]+):(?!=)\s*(?P<prerequisites>.*)$")
DESCRIPTION = "## "
WARNING = "Warning: "


@dataclass(frozen=True)
class Rule:
    description: str
    warning: bool
    prerequisites: list[str]
    recipe: bool


def rules(makefile: str) -> dict[str, Rule]:
    lines = makefile.replace("\\\n", " ").splitlines()
    result: dict[str, Rule] = {}
    for i, line in enumerate(lines):
        if match := RULE.match(line):
            above = lines[i - 1] if i > 0 else ""
            description = above.removeprefix(DESCRIPTION) if above.startswith(DESCRIPTION) else ""
            prerequisites = [p for p in match["prerequisites"].split() if not p.startswith("$")]
            recipe = i + 1 < len(lines) and lines[i + 1].startswith("\t")
            warning = description.startswith(WARNING)
            result[match["target"]] = Rule(
                description.removeprefix(WARNING), warning, prerequisites, recipe
            )
    return result


def makefile_rules() -> dict[str, Rule]:
    """Rules of the Makefile in the working directory"""
    return rules(pathlib.Path("Makefile").read_text())
