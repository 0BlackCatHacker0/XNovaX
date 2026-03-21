#!/bin/bash
echo "=== GOD MODE: NOVAX SELF-UPGRADE SWARM ==="
echo "Each provider analyzes a different NovaX subsystem"
echo ""

TOTAL_TOK=0
OK_COUNT=0

run_query() {
  local label="$1"
  local provider="$2"
  local prompt="$3"
  local timeout="$4"
  echo "[$label] $provider..."
  local result=$(curl -s -X POST http://127.0.0.1:9878/query -H "Content-Type: application/json" \
    -d "{\"prompt\": \"$prompt\", \"provider\": \"$provider\"}" --max-time "$timeout" 2>&1)
  local t=$(echo "$result" | grep -o '"tokens":[0-9]*' | tail -1 | cut -d: -f2)
  local c=$(echo "$result" | grep -o '"cascade_depth":0' | head -1)
  if [ -n "$c" ] && [ -n "$t" ] && [ "$t" -gt 0 ] 2>/dev/null; then
    OK_COUNT=$((OK_COUNT+1))
    TOTAL_TOK=$((TOTAL_TOK+t))
    echo "  DIRECT HIT: $t tokens"
  else
    echo "  cascaded or failed"
  fi
}

run_query "1/9 Cloud Router" "cerebras_direct" \
  "Design a parallel provider racing algorithm for an AI cloud router. When a query arrives, fan out to 3 providers simultaneously and return the first successful response. Write the race_providers function in pseudocode with timeout handling and cancellation." 30

run_query "2/9 Token Tracking" "openai" \
  "Design a hierarchical token accounting system for a multi-provider AI OS. Track per-provider daily totals, per-model usage, rate limit proximity. Output the data structure and 3 key functions." 45

run_query "3/9 Swarm Intelligence" "together" \
  "Design a swarm intelligence algorithm for 510000 models across 29 providers. Goals: maximize token output, minimize latency, avoid rate limits. Write model selection and load balancing pseudocode." 45

run_query "4/9 Error Handling" "groq" \
  "Design error handling for an AI OS with 97 microservices. Handle: service crashes, API rate limits, network timeouts, cascade failures. Write 4 handler functions in pseudocode." 45

run_query "5/9 Ternary Optimization" "mistral" \
  "Optimize binary-to-ternary conversion for an AI OS. Design: fast converter, ternary quantization of confidence scores, ternary error correction. Include algorithms." 45

run_query "6/9 Fractal Engine" "deepseek" \
  "Enhance a fractal task decomposition engine. Add recursive splitting with depth control, subtask dependency graphs, result synthesis. Write the recursive algorithm." 45

run_query "7/9 Response Merging" "cohere" \
  "Design a response merging algorithm for multi-model swarm. When 9 models answer the same question, merge into one coherent answer. Write semantic dedup and consensus extraction pseudocode." 45

run_query "8/9 Health Monitoring" "openrouter" \
  "Design real-time provider health monitoring for 29 cloud providers. Track response times, error rates, quality scores. Write health score calculation and circuit breaker algorithms." 45

run_query "9/9 HiveMind Architecture" "cerebras_direct" \
  "Redesign a HiveMind with 573 models. Add parallel dispatch, domain-aware routing, weighted response synthesis. Write the architecture and key algorithms." 30

echo ""
echo "================================================================"
echo "  GOD MODE SWARM COMPLETE"
echo "  Providers hit direct: $OK_COUNT / 9"
echo "  Total tokens generated: $TOTAL_TOK"
echo "================================================================"
echo ""
curl -s http://127.0.0.1:9878/health 2>&1 | grep -o '"total_tokens":[0-9]*\|"queries":[0-9]*\|"successful":[0-9]*'
