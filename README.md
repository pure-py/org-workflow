# org-workflow

[![status page](https://github.com/pure-py/org-workflow/actions/workflows/status.yml/badge.svg)](https://pure-py.github.io/org-workflow/status.html)

Dependency diagram, open pull requests and org-wide project integrity, published hourly to GitHub Pages.

## Project structure

- `script/diagram/`: dependency diagram, with a module for each kind of project in `node/` and each kind of
  dependency in `edge/`
- `script/check-project-integrity.sh`: integrity rules for the project board and the issues of every repository
- `script/status-page.py`: status page, with the diagram, open pull requests and integrity report

## Building

`make status.html` builds the page from clones of the organisation's repositories alongside this one. It needs
[D2](https://d2lang.com), and `GH_TOKEN` set to a token with read access to the organisation's projects; the
workflow reads the project board with the `PROJECT_PAT` secret.
