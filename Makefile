default: status.html

## Dependency diagram of the organisation's repositories, from clones alongside this repository
dependencies.svg:
	PYTHONPATH=script uv run --locked python -m diagram .. $@

## Project integrity report
integrity.txt:
	-script/check-project-integrity.sh pure-py pure-py-spec 1 "In progress,Awaiting Review" > $@

## Status page
status.html: dependencies.svg integrity.txt
	uv run --locked python script/status-page.py .. integrity.txt > $@
