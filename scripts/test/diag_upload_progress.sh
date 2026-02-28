#!/usr/bin/env bash

set -u

BASE_URL="https://costmatrix.yhroot.com"
FILE_PATH="/Users/guoliang/Desktop/workspace/code/GalaxySpace/GalaxySpaceAI/CostMatrix/tesdata/9月份考勤数据统计与分析1.xlsx"
USERNAME="admin"
PASSWORD="admin123"
TOKEN=""
MAX_POLLS=120
INTERVAL=1
INSECURE=0

HTTP_200=0
HTTP_404=0
HTTP_OTHER=0
TMP_DIR=""

print_usage() {
  cat <<'EOF'
Usage:
  scripts/diag_upload_progress.sh -f <excel_file> [options]

Required:
  -f, --file <path>         Excel file path (.xlsx/.xls)

Options:
  -u, --url <base_url>      Base URL (default: https://costmatrix.yhroot.com)
  -n, --username <name>     Login username (optional)
  -p, --password <pass>     Login password (optional, used with username)
  -t, --token <jwt>         Bearer token (optional, overrides login)
  -m, --max-polls <num>     Max progress polls (default: 120)
  -i, --interval <sec>      Poll interval seconds (default: 1)
  -k, --insecure            Allow insecure TLS
  -h, --help                Show this help

Examples:
  scripts/diag_upload_progress.sh -f /tmp/test.xlsx
  scripts/diag_upload_progress.sh -f /tmp/test.xlsx -u https://costmatrix.yhroot.com
  scripts/diag_upload_progress.sh -f /tmp/test.xlsx -n admin -p 'your_password'
EOF
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $cmd" >&2
    exit 1
  fi
}

now() {
  date '+%F %T'
}

json_get() {
  local file="$1"
  local expr="$2"
  python3 - "$file" "$expr" <<'PY'
import json
import sys

path = sys.argv[2].split(".")
try:
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)
    cur = data
    for p in path:
        if p == "":
            continue
        if isinstance(cur, dict):
            cur = cur.get(p, None)
        else:
            cur = None
            break
    if cur is None:
        print("")
    elif isinstance(cur, (dict, list)):
        print(json.dumps(cur, ensure_ascii=False))
    else:
        print(cur)
except Exception:
    print("")
PY
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -f|--file)
        FILE_PATH="${2:-}"
        shift 2
        ;;
      -u|--url)
        BASE_URL="${2:-}"
        shift 2
        ;;
      -n|--username)
        USERNAME="${2:-}"
        shift 2
        ;;
      -p|--password)
        PASSWORD="${2:-}"
        shift 2
        ;;
      -t|--token)
        TOKEN="${2:-}"
        shift 2
        ;;
      -m|--max-polls)
        MAX_POLLS="${2:-}"
        shift 2
        ;;
      -i|--interval)
        INTERVAL="${2:-}"
        shift 2
        ;;
      -k|--insecure)
        INSECURE=1
        shift
        ;;
      -h|--help)
        print_usage
        exit 0
        ;;
      *)
        echo "ERROR: unknown argument: $1" >&2
        print_usage
        exit 1
        ;;
    esac
  done
}

run_health_check() {
  local body_file="$1"
  local code
  local -a cargs
  cargs=(-sS)
  if [[ "$INSECURE" -eq 1 ]]; then
    cargs+=(-k)
  fi
  code=$(curl "${cargs[@]}" -o "$body_file" -w '%{http_code}' "${BASE_URL%/}/api/health" || true)
  echo "[$(now)] health HTTP=${code} body=$(cat "$body_file")"
}

run_login_if_needed() {
  if [[ -n "$TOKEN" ]]; then
    return 0
  fi

  if [[ -z "$USERNAME" || -z "$PASSWORD" ]]; then
    return 0
  fi

  local body_file="$1"
  local code
  local -a cargs
  cargs=(-sS)
  if [[ "$INSECURE" -eq 1 ]]; then
    cargs+=(-k)
  fi
  code=$(curl "${cargs[@]}" \
    -H "Content-Type: application/json" \
    -X POST \
    -d "{\"username\":\"${USERNAME}\",\"password\":\"${PASSWORD}\"}" \
    -o "$body_file" \
    -w '%{http_code}' \
    "${BASE_URL%/}/api/login" || true)

  echo "[$(now)] login HTTP=${code}"
  TOKEN="$(json_get "$body_file" "access_token")"
  if [[ -z "$TOKEN" ]]; then
    echo "[$(now)] WARN: login did not return access_token; continuing without token"
  else
    echo "[$(now)] login token acquired (length=${#TOKEN})"
  fi
}

run_upload() {
  local body_file="$1"
  local code
  local -a cargs
  cargs=(-sS)
  if [[ "$INSECURE" -eq 1 ]]; then
    cargs+=(-k)
  fi

  local -a req
  req=("${cargs[@]}" -X POST -F "file=@${FILE_PATH}")
  if [[ -n "$TOKEN" ]]; then
    req+=(-H "Authorization: Bearer ${TOKEN}")
  fi
  req+=(-o "$body_file" -w '%{http_code}' "${BASE_URL%/}/api/upload")

  code=$(curl "${req[@]}" || true)
  echo "$code"
}

run_progress_poll() {
  local task_id="$1"
  local body_file="$2"
  local code
  local -a cargs
  cargs=(-sS)
  if [[ "$INSECURE" -eq 1 ]]; then
    cargs+=(-k)
  fi

  local -a req
  req=("${cargs[@]}")
  if [[ -n "$TOKEN" ]]; then
    req+=(-H "Authorization: Bearer ${TOKEN}")
  fi
  req+=(-o "$body_file" -w '%{http_code}' "${BASE_URL%/}/api/progress/${task_id}")

  code=$(curl "${req[@]}" || true)
  echo "$code"
}

main() {
  parse_args "$@"

  require_cmd curl
  require_cmd python3

  if [[ -z "$FILE_PATH" ]]; then
    echo "ERROR: missing required --file" >&2
    print_usage
    exit 1
  fi
  if [[ ! -f "$FILE_PATH" ]]; then
    echo "ERROR: file not found: $FILE_PATH" >&2
    exit 1
  fi

  TMP_DIR="$(mktemp -d)"
  trap '[[ -n "${TMP_DIR:-}" ]] && rm -rf "$TMP_DIR"' EXIT

  local health_body login_body upload_body progress_body
  health_body="${TMP_DIR}/health.json"
  login_body="${TMP_DIR}/login.json"
  upload_body="${TMP_DIR}/upload.json"
  progress_body="${TMP_DIR}/progress.json"

  echo "[$(now)] start diagnose"
  echo "base_url=${BASE_URL}"
  echo "file=${FILE_PATH}"
  echo "max_polls=${MAX_POLLS}, interval=${INTERVAL}s"

  run_health_check "$health_body"
  run_login_if_needed "$login_body"

  local upload_code
  upload_code="$(run_upload "$upload_body")"
  echo "[$(now)] upload HTTP=${upload_code} body=$(cat "$upload_body")"

  local task_id
  task_id="$(json_get "$upload_body" "data.task_id")"
  if [[ -z "$task_id" ]]; then
    echo "[$(now)] ERROR: task_id not found in upload response"
    exit 2
  fi

  echo "[$(now)] task_id=${task_id}"
  echo "[$(now)] begin polling..."

  local i status progress step
  for ((i=1; i<=MAX_POLLS; i++)); do
    local code
    code="$(run_progress_poll "$task_id" "$progress_body")"

    if [[ "$code" == "200" ]]; then
      HTTP_200=$((HTTP_200 + 1))
      status="$(json_get "$progress_body" "data.status")"
      progress="$(json_get "$progress_body" "data.progress")"
      step="$(json_get "$progress_body" "data.current_step")"
      echo "[$(now)] poll#${i} HTTP=200 status=${status:-unknown} progress=${progress:-?} step=${step:-}"
      if [[ "$status" == "completed" || "$status" == "failed" ]]; then
        break
      fi
    elif [[ "$code" == "404" ]]; then
      HTTP_404=$((HTTP_404 + 1))
      echo "[$(now)] poll#${i} HTTP=404 body=$(cat "$progress_body")"
    else
      HTTP_OTHER=$((HTTP_OTHER + 1))
      echo "[$(now)] poll#${i} HTTP=${code} body=$(cat "$progress_body")"
    fi

    sleep "$INTERVAL"
  done

  local total
  total=$((HTTP_200 + HTTP_404 + HTTP_OTHER))

  echo "[$(now)] ===== Summary ====="
  echo "task_id=${task_id}"
  echo "poll_total=${total}"
  echo "http_200=${HTTP_200}"
  echo "http_404=${HTTP_404}"
  echo "http_other=${HTTP_OTHER}"

  if [[ "$HTTP_404" -gt 0 && "$HTTP_200" -gt 0 ]]; then
    echo "diagnosis=Likely multi-worker/load-balancer with in-memory task state (same task gets 200 and 404)."
  elif [[ "$HTTP_404" -gt 0 && "$HTTP_200" -eq 0 ]]; then
    echo "diagnosis=Task missing for all polls; check upload response, backend restart, or route mismatch."
  else
    echo "diagnosis=No 404 seen in this run."
  fi
}

main "$@"
