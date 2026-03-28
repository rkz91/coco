#!/bin/bash
# Smoke test all API endpoints
BASE="http://localhost:8000"
PASS=0
FAIL=0

check() {
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE$1")
  if [ "$STATUS" = "$2" ]; then
    echo "  ✓ $1 -> $STATUS"
    PASS=$((PASS + 1))
  else
    echo "  ✗ $1 -> $STATUS (expected $2)"
    FAIL=$((FAIL + 1))
  fi
}

check_post() {
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -d "$3" "$BASE$1")
  if [ "$STATUS" = "$2" ]; then
    echo "  ✓ POST $1 -> $STATUS"
    PASS=$((PASS + 1))
  else
    echo "  ✗ POST $1 -> $STATUS (expected $2)"
    FAIL=$((FAIL + 1))
  fi
}

echo "Smoke testing CoCo Platform..."
echo ""
echo "--- Core ---"
check "/api/health" "200"
check "/api/dashboard" "200"
check "/api/home" "200"
check "/api/settings" "200"

echo ""
echo "--- Data ---"
check "/api/projects" "200"
check "/api/content?limit=5" "200"
check "/api/agents" "200"
check "/api/agent-roles" "200"
check "/api/tasks" "200"
check "/api/todos" "200"
check "/api/drafts" "200"
check "/api/goals" "200"
check "/api/teams" "200"
check "/api/tree" "200"

echo ""
echo "--- Brain & Queue ---"
check "/api/queue" "200"
check "/api/brain" "200"
check "/api/brain/people" "200"
check "/api/brain/rules" "200"
check "/api/config" "200"

echo ""
echo "--- Costs ---"
check "/api/costs/summary" "200"
check "/api/costs/events" "200"
check "/api/budgets" "200"

echo ""
echo "--- Sessions & Activity ---"
check "/api/sessions" "200"
check "/api/activity" "200"
check "/api/chat/history" "200"
check "/api/chat/sessions" "200"

echo ""
echo "--- Collaboration ---"
check "/api/workflow-templates" "200"
check "/api/nodes/root/context" "200"
check "/api/nodes/root/handoffs" "200"

echo ""
echo "--- Voice & Jarvis ---"
check "/api/tts/voices" "200"
check_post "/api/jarvis/command" "200" '{"text":"health"}'
check_post "/api/chat/sessions" "200" '{}'

echo ""
echo "Results: $PASS passed, $FAIL failed"
