#!/usr/bin/env bash
set -u

failures=0
warnings=0

check_command() {
    local command_name="$1"
    local required="$2"
    if command -v "$command_name" >/dev/null 2>&1; then
        printf 'OK       command %-12s %s\n' "$command_name" "$(command -v "$command_name")"
    elif [[ "$required" == "required" ]]; then
        printf 'MISSING  command %-12s required\n' "$command_name"
        failures=$((failures + 1))
    else
        printf 'OPTIONAL command %-12s not installed\n' "$command_name"
        warnings=$((warnings + 1))
    fi
}

printf 'Digital Secretariat preflight (read-only)\n'
printf 'OS       %s\n' "$(uname -srm)"
for name in git python3.11 openssl curl psql systemctl; do
    check_command "$name" required
done
check_command tailscale optional
check_command jq optional

python_version="$(python3.11 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))' 2>/dev/null || true)"
if [[ "$python_version" == "3.11" ]]; then
    printf 'OK       python       %s\n' "$python_version"
else
    printf 'MISSING  python       expected 3.11, found %s\n' "${python_version:-unknown}"
    failures=$((failures + 1))
fi

printf 'SUMMARY  failures=%s warnings=%s\n' "$failures" "$warnings"
exit "$failures"
