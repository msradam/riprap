#!/usr/bin/env bash
# Wake the riprap-triton GPU and block until vLLM reports ready. Run before a
# demo: LLM mode hard-fails if the planner's first call hits a cold vLLM.
set -u

PROXY_URL="${PROXY_URL:-https://msradam-riprap--riprap-triton-riprap-proxy.modal.run}"
: "${RIPRAP_PROXY_TOKEN:?export RIPRAP_PROXY_TOKEN (the riprap-stack proxy bearer) first}"

echo "waking GPU at $PROXY_URL (cold start ~100s on a warm Volume)..."
for i in $(seq 1 45); do
    resp=$(curl -s -m 30 -H "Authorization: Bearer $RIPRAP_PROXY_TOKEN" "$PROXY_URL/healthz" 2>/dev/null)
    if printf '%s' "$resp" | grep -q '"vllm": *"ok"'; then
        echo "ready: $resp"
        exit 0
    fi
    printf '  [%02d] not ready: %s\n' "$i" "${resp:0:80}"
    sleep 8
done
echo "timed out waiting for vllm:ok" >&2
exit 1
