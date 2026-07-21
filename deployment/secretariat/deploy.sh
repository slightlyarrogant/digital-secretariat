#!/usr/bin/env bash
set -euo pipefail

readonly install_config="${1:-/etc/digital-secretariat/install.conf}"

if [[ ! -r "$install_config" ]]; then
    echo "Missing readable install config: $install_config" >&2
    exit 1
fi

# shellcheck source=/dev/null
source "$install_config"

: "${APP_USER:?APP_USER is required}"
: "${APP_GROUP:?APP_GROUP is required}"
: "${INSTALL_ROOT:=/opt/digital-secretariat}"
: "${CONFIG_ROOT:=/etc/digital-secretariat}"
: "${PORT:=8040}"
: "${PYTHON:=$INSTALL_ROOT/venv/bin/python}"
: "${SMTP_IP_ALLOW:?SMTP_IP_ALLOW is required}"

readonly service_name="digital-secretariat.service"
readonly cache_service="digital-secretariat-mail-cache.service"
readonly cache_timer="digital-secretariat-mail-cache.timer"
repo_root="$(git rev-parse --show-toplevel)"
commit="$(git -C "$repo_root" rev-parse HEAD)"
release_dir="$INSTALL_ROOT/releases/$commit"
current_link="$INSTALL_ROOT/current"
stage_dir="$(mktemp -d)"
previous_release=""

cleanup() {
    rm -rf "$stage_dir"
}
trap cleanup EXIT

if [[ "$(id -u)" -ne 0 ]]; then
    echo "Run deploy.sh as root after the AI installer has reviewed the plan" >&2
    exit 1
fi
if ! git -C "$repo_root" diff --quiet || ! git -C "$repo_root" diff --cached --quiet; then
    echo "Refusing to deploy a dirty worktree" >&2
    exit 1
fi
for credential in database-url content-database-url action-database-url action-token-secret; do
    test -s "$CONFIG_ROOT/$credential"
    [[ "$(stat -c '%a' "$CONFIG_ROOT/$credential")" == "600" ]]
done
test -x "$PYTHON"

git -C "$repo_root" archive --format=tar "$commit" \
    src email-templates pyproject.toml | tar -xf - -C "$stage_dir"
install -d -o root -g root -m 0755 "$INSTALL_ROOT" "$INSTALL_ROOT/releases"
if [[ ! -d "$release_dir" ]]; then
    install -d -o root -g root -m 0755 "$release_dir"
    cp -a "$stage_dir/." "$release_dir/"
    chown -R root:root "$release_dir"
    chmod -R go-w "$release_dir"
fi

if [[ -L "$current_link" ]]; then
    previous_release="$(readlink -f "$current_link")"
fi
ln -sfn "$release_dir" "$INSTALL_ROOT/current.next"
mv -Tf "$INSTALL_ROOT/current.next" "$current_link"

render_unit() {
    local source="$1"
    local destination="$2"
    local rendered="$stage_dir/$(basename "$destination").rendered"
    local rules="$stage_dir/$(basename "$destination").smtp-rules"
    : > "$rules"
    for address in $SMTP_IP_ALLOW; do
        if [[ ! "$address" =~ ^[0-9A-Fa-f:.]+(/[0-9]{1,3})?$ ]]; then
            echo "Invalid SMTP_IP_ALLOW address: $address" >&2
            exit 1
        fi
        printf 'IPAddressAllow=%s\n' "$address" >> "$rules"
    done
    sed \
        -e "s|@APP_USER@|$APP_USER|g" \
        -e "s|@APP_GROUP@|$APP_GROUP|g" \
        -e "s|@INSTALL_ROOT@|$INSTALL_ROOT|g" \
        -e "s|@CONFIG_ROOT@|$CONFIG_ROOT|g" \
        -e "s|@PYTHON@|$PYTHON|g" \
        -e "s|@PORT@|$PORT|g" \
        "$source" > "$rendered"
    awk -v rules="$rules" '
        $0 == "@SMTP_IP_ALLOW_RULES@" {
            while ((getline line < rules) > 0) print line
            close(rules)
            next
        }
        { print }
    ' "$rendered" > "$destination"
    if grep -q '@[A-Z_][A-Z_]*@' "$destination"; then
        echo "Unresolved placeholder in $destination" >&2
        exit 1
    fi
    chmod 0644 "$destination"
    systemd-analyze verify "$destination"
}

render_unit "$repo_root/systemd/digital-secretariat.service.in" \
    "/etc/systemd/system/$service_name"
render_unit "$repo_root/systemd/digital-secretariat-mail-cache.service.in" \
    "/etc/systemd/system/$cache_service"
install -o root -g root -m 0644 "$repo_root/systemd/$cache_timer" \
    "/etc/systemd/system/$cache_timer"

systemctl daemon-reload
systemctl enable "$service_name" >/dev/null
systemctl enable --now "$cache_timer" >/dev/null

if systemctl restart "$service_name" \
    && systemctl start "$cache_service" \
    && curl --fail --silent --show-error --retry 10 --retry-delay 1 \
        --retry-connrefused "http://127.0.0.1:$PORT/health/ready" >/dev/null; then
    echo "Deployed $service_name at $commit"
    exit 0
fi

echo "Readiness failed; rolling back" >&2
if [[ -n "$previous_release" ]]; then
    ln -sfn "$previous_release" "$INSTALL_ROOT/current.next"
    mv -Tf "$INSTALL_ROOT/current.next" "$current_link"
    systemctl restart "$service_name"
else
    systemctl stop "$service_name"
fi
exit 1
