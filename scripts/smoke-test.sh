#!/usr/bin/env bash
# Demo the ledger's cross-meeting intelligence: fire THREE meetings at the same
# workspace and watch state accumulate — a commitment gets fulfilled and a
# decision gets superseded across meetings. Run scripts/run-local.sh first.
set -euo pipefail
URL=${URL:-http://localhost:9000}
WS=${WS:-demo-team}

post() {
  curl -s -X POST "$URL/test" -H 'Content-Type: application/json' -d "$1" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print('\n'.join('  · '+l for l in d['logs'])); print(d['artifacts'][0]['content'])"
}

echo "════════ Meeting 1: Kickoff ════════"
post '{
  "task": {"id":"m1","title":"Kickoff","description":""},
  "summary":"We decided to build the MVP on Postgres. Alice will set up the CI pipeline by Friday. Bob raised that the pricing tier is still unclear.",
  "attendees":[{"id":"a1","name":"Alice"},{"id":"a2","name":"Bob"}],
  "agent":{"instructions":"workspace: '"$WS"'","tools":[],"model":"llama3.1:8b"}
}'

echo -e "\n════════ Meeting 2: Sprint review (CI done, DB reversed) ════════"
post '{
  "task": {"id":"m2","title":"Sprint 1 review","description":""},
  "summary":"Alice finished the CI pipeline, it is green. We reversed the earlier call and will switch storage to MySQL for ops reasons. Bob will write the onboarding docs next week.",
  "attendees":[{"id":"a1","name":"Alice"},{"id":"a2","name":"Bob"}],
  "agent":{"instructions":"workspace: '"$WS"'","tools":[],"model":"llama3.1:8b"}
}'

echo -e "\n════════ Meeting 3: Sprint review (risk resolved) ════════"
post '{
  "task": {"id":"m3","title":"Sprint 2 review","description":""},
  "summary":"Pricing tier is confirmed as the Team plan, so that concern is closed. Carol will run the security review by Aug 1.",
  "attendees":[{"id":"a1","name":"Alice"},{"id":"a3","name":"Carol"}],
  "agent":{"instructions":"workspace: '"$WS"'","tools":[],"model":"llama3.1:8b"}
}'

echo -e "\n════════ The living ledger ════════"
echo "Open in a browser:  $URL/dashboard/$WS"
