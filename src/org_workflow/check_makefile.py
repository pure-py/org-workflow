"""Check that every target with a recipe in the Makefile of the working directory has a description, except the
special and internal targets starting with a dot. Exit with failure if any target lacks a description."""

from __future__ import annotations

import sys

from org_workflow.makefile import makefile_rules


def main() -> None:
    undescribed = [
        target
        for target, rule in makefile_rules().items()
        if rule.recipe and not rule.description and not target.startswith(".")
    ]
    for target in undescribed:
        print(f"{target}: not described")
    sys.exit(bool(undescribed))
