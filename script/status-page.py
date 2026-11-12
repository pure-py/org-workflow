#!/usr/bin/env python3
"""Status page of the organisation"""

from __future__ import annotations

import datetime
import html
import json
import pathlib
import re
import subprocess
import sys
import tempfile
from typing import Any

from diagram.edge import Edge

SUBMISSION_WORKFLOW = "submission.yml"
SUBMISSION_REPORT = "submission-report"
SUBMISSION_TARGET = "check-submission"
ISSUE = re.compile(r"(?P<repo>[\w.-]+)?#(?P<number>\d+)")
FIELDS = "number,title,url,author,isDraft,updatedAt,reviewDecision,statusCheckRollup"
FAILED = {"FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED"}
REVIEW = {
    "APPROVED": "approved",
    "CHANGES_REQUESTED": "changes requested",
    "REVIEW_REQUIRED": "review required",
}
STYLE = """
body { font-family: system-ui, sans-serif; max-width: 70em; margin: 2em auto; padding: 0 1em; }
img.diagram { width: 32em; max-width: 100%; }
img.badge { vertical-align: middle; }
tr.failed td { color: #e00000; }
tr.passed td { color: #008000; }
table { border-collapse: collapse; }
th, td { text-align: left; padding: 0.3em 0.6em; border-bottom: 1px solid #ccc; white-space: nowrap; }
td.title, table.submission td:nth-child(4) { white-space: normal; }
table.key { font-size: 0.8em; }
table.key td { border: none; padding: 0 0.5em; }
table.key svg { vertical-align: middle; }
table.integrity td:first-child { width: 12em; }
table.integrity td:nth-child(2) { width: 4em; }
"""


def display_name(org: str) -> str:
    view = ["gh", "api", f"orgs/{org}", "--jq", ".name // .login"]
    return subprocess.run(view, capture_output=True, text=True, check=True).stdout.strip()


def pull_requests(org: str, repo: str) -> list[dict[str, Any]]:
    listing = subprocess.run(
        ["gh", "pr", "list", "--repo", f"{org}/{repo}", "--state", "open", "--json", FIELDS],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    result: list[dict[str, Any]] = json.loads(listing)
    return result


def checks(pr: dict[str, Any]) -> str:
    outcomes = [check.get("conclusion") or check.get("state") for check in pr["statusCheckRollup"]]
    if not outcomes:
        return "none"
    if any(outcome in FAILED for outcome in outcomes):
        return "failing"
    if any(outcome in (None, "", "PENDING", "EXPECTED") for outcome in outcomes):
        return "running"
    return "passing"


def row(repo: str, pr: dict[str, Any]) -> str:
    cells = [
        repo,
        f'<a href="{pr["url"]}">#{pr["number"]}</a>',
        f'<a href="{pr["url"]}" class="title">{html.escape(pr["title"])}</a>',
        html.escape(pr["author"]["login"]),
        REVIEW.get(pr["reviewDecision"], "none"),
        checks(pr),
        pr["updatedAt"][:10],
    ]
    return (
        "<tr>"
        + "".join(
            f'<td class="title">{c}</td>' if 'class="title"' in c else f"<td>{c}</td>"
            for c in cells
        )
        + "</tr>\n"
    )


def integrity(org: str, report: str) -> str:
    rules: list[tuple[str, list[list[str]]]] = []
    for line in report.splitlines():
        if line.startswith("=== "):
            rules.append((line.strip("= "), []))
        elif "\t" in line:
            rules[-1][1].append(line.split("\t"))
    if not any(rows for _, rows in rules):
        return "<p>All rules passed.</p>"

    def cell(repo: str, text: str) -> str:
        """Link issue references in text, to repo unless qualified by a repository"""

        def link(m: re.Match[str]) -> str:
            url = f"https://github.com/{org}/{m['repo'] or repo}/issues/{m['number']}"
            return f'<a href="{url}">{m[0]}</a>'

        return ISSUE.sub(link, html.escape(text))

    def table(rows: list[list[str]]) -> str:
        headings = "".join(f"<th>{html.escape(h)}</th>" for h in rows[0])
        body = "".join(
            "<tr>" + "".join(f"<td>{cell(row[0], c)}</td>" for c in row) + "</tr>\n"
            for row in rows[1:]
        )
        return f'<table class="integrity">\n<tr>{headings}</tr>\n{body}</table>'

    return "\n".join(f"<h3>{html.escape(rule)}</h3>\n{table(rows)}" for rule, rows in rules if rows)


def description(makefile: pathlib.Path, target: str) -> str:
    """Double-hash comment above target's rule in makefile"""
    lines = makefile.read_text().splitlines()
    above = next(lines[i - 1] for i, line in enumerate(lines) if line.startswith(f"{target}:"))
    assert above.startswith("## "), f"{target} has no description"
    return above.removeprefix("## ")


def arrow(colour: str, dash: int) -> str:
    pattern = f' stroke-dasharray="{dash + 2} {dash}"' if dash else ""
    return (
        '<svg width="36" height="10">'
        f'<line x1="0" y1="5" x2="26" y2="5" stroke="{colour}" stroke-width="1.5"{pattern}/>'
        f'<polygon points="26,1 36,5 26,9" fill="{colour}"/></svg>'
    )


KEY = [
    (arrow(style.colour, style.dash), style.key_text)
    for kind in Edge.kinds()
    for style in kind.styles
]


def submission(org: str, repo: str) -> str:
    """Submission section built from the latest completed run on main of repo"""
    listing = subprocess.run(
        ["gh", "run", "list", "--repo", f"{org}/{repo}", "--workflow", SUBMISSION_WORKFLOW]
        + ["--branch", "main", "--status", "completed", "--limit", "1"]
        + ["--json", "databaseId,conclusion,createdAt,url"],
        capture_output=True,
        text=True,
        check=False,
    )
    runs: list[dict[str, Any]] = json.loads(listing.stdout) if listing.returncode == 0 else []
    if not runs:
        return "<p>No run yet.</p>"
    run = runs[0]
    with tempfile.TemporaryDirectory() as directory:
        subprocess.run(
            ["gh", "run", "download", str(run["databaseId"]), "--repo", f"{org}/{repo}"]
            + ["--name", SUBMISSION_REPORT, "--dir", directory],
            capture_output=True,
            check=False,
        )
        report = pathlib.Path(directory, "submission.tsv")
        rows = (
            [line.split("\t") for line in report.read_text().splitlines()]
            if report.exists()
            else []
        )
    when = run["createdAt"][:16].replace("T", " ")
    badge = f"https://github.com/{org}/{repo}/actions/workflows/{SUBMISSION_WORKFLOW}/badge.svg?branch=main"
    heading = (
        f'<p><a href="{run["url"]}"><img class="badge" src="{badge}" alt="{html.escape(run["conclusion"])}"></a>'
        f" {when} UTC</p>"
    )
    body = "".join(
        (f'<tr class="{row[2]}">' if row[2] in ("passed", "failed") else "<tr>")
        + "".join(f"<td>{html.escape(c)}</td>" for c in row)
        + "</tr>\n"
        for row in rows
    )
    return f'{heading}\n<table class="submission">\n<tr><th>Target</th><th>Check</th><th>Result</th><th>Detail</th></tr>\n{body}</table>'


def submissions(org: str, root: pathlib.Path, repos: list[str]) -> str:
    """Submission section for each repository with a submission workflow"""
    return "".join(
        f"<h2>{html.escape(description(root / repo / 'Makefile', SUBMISSION_TARGET))} status</h2>\n"
        f"{submission(org, repo)}\n"
        for repo in repos
        if (root / repo / ".github" / "workflows" / SUBMISSION_WORKFLOW).exists()
    )


def page(org: str, root: pathlib.Path, report: str) -> str:
    repos = sorted(path.name for path in root.iterdir() if (path / ".git").exists())
    prs = [(name, pr) for name in repos for pr in pull_requests(org, name)]
    title = f"{html.escape(display_name(org))} status"
    updated = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M")

    def table(draft: bool) -> str:
        rows = "".join(row(name, pr) for name, pr in prs if pr["isDraft"] == draft)
        return f"""<table>
<tr><th>Repository</th><th>#</th><th>Title</th><th>Author</th><th>Review</th><th>Checks</th><th>Updated</th></tr>
{rows}</table>"""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>{STYLE}</style>
</head>
<body>
<h1>{title}</h1>
{submissions(org, root, repos)}<h2>Dependencies</h2>
<p>Updated <time>{updated}</time> UTC.</p>
<img class="diagram" src="dependencies.svg" alt="Dependencies between repositories">
<table class="key">
{"".join(f"<tr><td>{a}</td><td>{label}</td></tr>" for a, label in KEY)}
</table>
<h2>Open pull requests</h2>
{table(draft=False)}
<h2>Draft pull requests</h2>
{table(draft=True)}
<h2>Project integrity</h2>
{integrity(org, report)}
</body>
</html>
"""


def main() -> None:
    org, root, report = sys.argv[1:]
    sys.stdout.write(page(org, pathlib.Path(root), pathlib.Path(report).read_text()))


if __name__ == "__main__":
    main()
