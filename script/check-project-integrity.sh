#!/usr/bin/env bash
set -eo pipefail

if [ $# -ne 3 ]; then
  echo "Usage: $0 <organisation> <project number> <comma-separated Statuses whose issues must have a milestone>" >&2
  exit 1
fi

ORG="$1"
PROJECT="$2"
ACTIVE="$3"
ERRORS=0

echo "Checking project integrity for $ORG (project $PROJECT)..."

REPOS=$(gh repo list "$ORG" --no-archived --limit 1000 --json name --jq '.[].name')

# Issues of every repository in the given state, with the given fields
issues() {
  local state="$1"
  local fields="$2"
  for repo in $REPOS; do
    gh api graphql --paginate -f org="$ORG" -f repo="$repo" -f query='
      query($endCursor: String, $org: String!, $repo: String!) {
        repository(owner: $org, name: $repo) {
          issues(first: 100, states: '"$state"', after: $endCursor) {
            pageInfo { hasNextPage endCursor }
            nodes { number title repository { name } '"$fields"' }
          }
        }
      }
    ' --jq '.data.repository.issues.nodes[]' || exit 1
  done | jq -cs 'sort_by(.repository.name, .number)'
}

ALL_ITEMS=$(gh api graphql --paginate -f org="$ORG" -F project="$PROJECT" -f query='
  query($endCursor: String, $org: String!, $project: Int!) {
    organization(login: $org) {
      projectV2(number: $project) {
        items(first: 100, after: $endCursor) {
          pageInfo { hasNextPage endCursor }
          nodes {
            fieldValueByName(name: "Status") {
              ... on ProjectV2ItemFieldSingleSelectValue { name }
            }
            content {
              ... on Issue {
                number
                title
                state
                milestone { title state }
                repository { name }
              }
            }
          }
        }
      }
    }
  }
' --jq '.data.organization.projectV2.items.nodes[] | select(.content.number != null)' |
  jq -cs 'sort_by(.content.repository.name, .content.number)')

CLOSED_ISSUES=$(issues CLOSED 'subIssues(first: 100) { nodes { number state repository { name } } }')
OPEN_ISSUES=$(issues OPEN '')

ON_BOARD=$(echo "$ALL_ITEMS" | jq -c 'map("\(.content.repository.name)#\(.content.number)")')
ACTIVE_STATUSES=$(jq -cn --arg s "$ACTIVE" '$s | split(",") | map(ltrimstr(" ") | rtrimstr(" "))')

check() {
  local rule="$1"
  local headings="$2"
  local items="$3"
  local filter="$4"
  local fmt="$5"
  local found=0

  echo ""
  echo "=== $rule ==="
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    [ "$found" -eq 0 ] && printf '%s\n' "$headings"
    found=1
    printf '%s\n' "$line"
    ERRORS=$((ERRORS + 1))
  done < <(echo "$items" | jq -r ".[] | $filter | $fmt")
}

check "Open issues missing from the project board" $'Repository\tIssue\tTitle' "$OPEN_ISSUES" \
  'select("\(.repository.name)#\(.number)" as $i | '"$ON_BOARD"' | index($i) | not)' \
  '"\(.repository.name)\t#\(.number)\t\(.title)"'

check "Open issues without a Status" $'Repository\tIssue\tTitle' "$ALL_ITEMS" \
  'select(.content.state == "OPEN" and .fieldValueByName == null)' \
  '"\(.content.repository.name)\t#\(.content.number)\t\(.content.title)"'

check "Milestoned issues marked Proposed" $'Repository\tIssue\tTitle\tMilestone' "$ALL_ITEMS" \
  'select(.content.state == "OPEN" and .content.milestone != null and .fieldValueByName.name == "Proposed")' \
  '"\(.content.repository.name)\t#\(.content.number)\t\(.content.title)\t\(.content.milestone.title)"'

check "Active issues without a milestone" $'Repository\tIssue\tTitle\tStatus' "$ALL_ITEMS" \
  'select(.content.state == "OPEN" and .content.milestone == null and (.fieldValueByName.name as $s | '"$ACTIVE_STATUSES"' | index($s)))' \
  '"\(.content.repository.name)\t#\(.content.number)\t\(.content.title)\t\(.fieldValueByName.name)"'

check "Issues in closed milestones that aren't Done or Rejected" $'Repository\tIssue\tTitle\tStatus\tMilestone' "$ALL_ITEMS" \
  'select(.content.milestone.state == "CLOSED" and (.fieldValueByName.name != "Done" and .fieldValueByName.name != "Rejected"))' \
  '"\(.content.repository.name)\t#\(.content.number)\t\(.content.title)\t\(.fieldValueByName.name // "none")\t\(.content.milestone.title)"'

# Qualify a sub-issue in another repository by its repository
check "Closed issues with open sub-issues" $'Repository\tIssue\tTitle\tOpen sub-issues' "$CLOSED_ISSUES" \
  'select(any(.subIssues.nodes[]; .state == "OPEN"))' \
  '.repository.name as $r | "\($r)\t#\(.number)\t\(.title)\t\([.subIssues.nodes[] | select(.state == "OPEN") | if .repository.name == $r then "#\(.number)" else "\(.repository.name)#\(.number)" end] | join(", "))"'

echo ""
if [ "$ERRORS" -eq 0 ]; then
  echo "All checks passed."
else
  echo "$ERRORS issue(s) found."
  exit 1
fi
