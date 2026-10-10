#!/usr/bin/env bash
# LARE backend entrypoint. Reads backend/services.txt (the single source of
# truth for name/dir/port), initialises each service's schema, writes a
# supervisord program per service, then runs them all — the container twin of
# run-all.ps1. Env (DATABASE_URL, JWT secrets, API keys, REDIS_URL) is supplied
# by docker-compose's env_file and inherited by every child process.
set -euo pipefail

ROOT=/app/backend
if [[ -n "${SERVICE_REGISTRY_PATH:-}" ]]; then
  REGISTRY="$SERVICE_REGISTRY_PATH"
else
  case "${APP_PRODUCT:-combined}" in
    learn|hire) REGISTRY="$ROOT/services.${APP_PRODUCT}.txt" ;;
    combined) REGISTRY="$ROOT/services.txt" ;;
    *) echo "[entrypoint] ERROR: invalid APP_PRODUCT" >&2; exit 2 ;;
  esac
fi
# Write to the default path so `supervisorctl` (no -c) finds the socket too.
CONF=/etc/supervisor/supervisord.conf

# Postgres/Supabase reserve these schema names, so run-all.ps1 prefixes them
# with "lare_". Mirror that exactly (only "auth" collides in our registry).
reserved=" auth storage realtime graphql vault cron net extensions "
schema_for() {
  local name="${1//-/_}"
  case "$name" in
    coding|notification|files|analytics|audit|ai_orchestration|organization)
      if [[ "${APP_PRODUCT:-combined}" == "combined" ]]; then echo "$name";
      else echo "${APP_PRODUCT}_${name}"; fi
      return ;;
  esac
  if [[ "$reserved" == *" $name "* ]]; then echo "lare_${name}"; else echo "$name"; fi
}

if [[ -n "${DATABASE_URL:-}" ]]; then
  echo "[entrypoint] database URL configured"
else
  echo "[entrypoint] ERROR: DATABASE_URL is not configured" >&2
  exit 1
fi

# ---- 1. init-db for every selected service (idempotent; creates schema) ------
if [[ "${SKIP_INIT:-0}" != "1" ]]; then
  while read -r name dir port; do
    [[ -z "${name:-}" || "$name" == \#* ]] && continue
    [[ "$name" == "gateway" ]] && continue   # gateway is stateless
    local_schema="$(schema_for "$name")"
    echo "[entrypoint] init-db $name (schema=$local_schema)"
    ( cd "$ROOT/services/$dir" \
      && DB_SCHEMA="$local_schema" SERVICE_NAME="$name" PORT="$port" \
         python manage.py init-db ) \
      || { echo "[entrypoint] ERROR: init-db failed for $name" >&2; exit 1; }
  done < <(tr -d '\r' < "$REGISTRY")

  # Old certificate verification URLs used a short, enumerable code. Rotate
  # them only as part of an explicit schema initialization/migration pass.
  if [[ -d "$ROOT/services/certification" ]]; then
    ( cd "$ROOT/services/certification" \
      && DB_SCHEMA="$(schema_for certification)" SERVICE_NAME=certification \
         python manage.py migrate-verify-ids )
  fi
else
  echo "[entrypoint] SKIP_INIT=1; skipping schema initialization and migrations"
fi

# ---- 2. generate one supervisord [program] per service -----------------------
mkdir -p /etc/supervisor /var/log/lare
cat > "$CONF" <<'HEADER'
[supervisord]
nodaemon=true
logfile=/dev/null
logfile_maxbytes=0

[unix_http_server]
file=/var/run/supervisor.sock
chmod=0700

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[supervisorctl]
serverurl=unix:///var/run/supervisor.sock
HEADER

while read -r name dir port; do
  [[ -z "${name:-}" || "$name" == \#* ]] && continue
  extra_env=""
  if [[ "$name" != "gateway" ]]; then
    extra_env=",DB_SCHEMA=\"$(schema_for "$name")\""
    if [[ "$name" == "auth" && "${APP_PRODUCT:-combined}" != "combined" ]]; then
      extra_env+=",AUTH_ALLOWED_PRODUCT=\"${APP_PRODUCT}\""
    fi
  else
    port="${PORT:-10000}"
    extra_env=',HOST="0.0.0.0"'
  fi
  cat >> "$CONF" <<PROG

[program:$name]
command=python manage.py serve
directory=$ROOT/services/$dir
environment=PORT="$port",SERVICE_NAME="$name"$extra_env
autostart=true
autorestart=true
startsecs=3
stopsignal=TERM
stopwaitsecs=20
stopasgroup=true
killasgroup=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
PROG
done < <(tr -d '\r' < "$REGISTRY")

echo "[entrypoint] launching selected service registry: $REGISTRY"
exec supervisord -c "$CONF" -n
