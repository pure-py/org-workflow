"""Check that every target with a recipe is described, except targets starting with a dot"""

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
