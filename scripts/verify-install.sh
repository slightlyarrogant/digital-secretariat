#!/usr/bin/env bash
set -euo pipefail

readonly port="${PORT:-8040}"
readonly service="${SERVICE_NAME:-digital-secretariat.service}"

systemctl is-active --quiet "$service"
curl --fail --silent --show-error "http://127.0.0.1:$port/health/live" >/dev/null
curl --fail --silent --show-error "http://127.0.0.1:$port/health/ready" >/dev/null
ss -lnt | awk -v port=":$port" '$4 ~ port {print $4}' | grep -qx "127.0.0.1:$port"

printf 'OK service=%s bind=127.0.0.1:%s\n' "$service" "$port"
