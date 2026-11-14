#!/usr/bin/env bash
# Backup demo: feeds the local sample reports to the running app, one every $DELAY seconds.
set -euo pipefail
cd "$(dirname "$0")"
URL="${MUSTER_URL:-http://127.0.0.1:8000}"
curl -s -X POST "$URL/reset" >/dev/null
while IFS= read -r line; do
  [ -z "$line" ] && continue
  echo ">> $line"
  python3 -c 'import json,sys; print(json.dumps({"text": sys.argv[1]}))' "$line" \
    | curl -s -X POST "$URL/intake" -H 'Content-Type: application/json' --data-binary @- \
    | python3 -c 'import sys,json; d=json.load(sys.stdin); r=d.get("record"); print("  ", r["triage"]["priority"], r["uplink"]) if r else print("   ERROR", d)'
  sleep "${DELAY:-6}"
done < demo_lines.txt
