ORG := pure-py
# Repository with the submission workflow
SUBMISSION_REPO := pure-py-spec
PROJECT := 1
# Statuses whose issues must have a milestone
ACTIVE := In progress,Awaiting Review

default: status.html

## Dependency diagram of the organisation's repositories, from clones alongside this repository
dependencies.svg:
	PYTHONPATH=script uv run --locked python -m diagram $(ORG) .. $@

## Project integrity report
integrity.txt:
	-script/check-project-integrity.sh $(ORG) $(PROJECT) "$(ACTIVE)" > $@

## Status page
status.html: dependencies.svg integrity.txt
	uv run --locked python script/status-page.py $(ORG) $(SUBMISSION_REPO) .. integrity.txt > $@

.PHONY: default dependencies.svg integrity.txt status.html
