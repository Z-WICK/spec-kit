#!/usr/bin/env bash

# Guard script for /speckit.clarify.
# Ensures clarification updates remain anchored and do not drift original requirements.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: clarify-requirement-guard.sh --before <spec-before> --after <spec-after> [options]

Required:
  --before <path>                 Baseline spec snapshot before clarify edits
  --after <path>                  Spec file after clarify edits

Optional:
  --allow-non-clarification-change
                                  Allow content changes outside "## Clarifications"
  --min-clarifications <n>        Minimum clarification entries required (default: 1)
  --json                          Emit JSON output
  --help                          Show help
EOF
}

before_spec=""
after_spec=""
allow_non_clarification_change=false
min_clarifications=1
json_mode=false

json_escape() {
  printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
}

emit_fail() {
  local message=$1
  if $json_mode; then
    printf '{"ok":false,"error":"%s"}\n' "$(json_escape "$message")"
  else
    echo "ERROR: $message" >&2
  fi
  exit 1
}

emit_ok() {
  local non_clar_changed=$1
  local clarification_count=$2
  local source_tagged_count=$3
  if $json_mode; then
    printf '{"ok":true,"non_clarification_changed":%s,"clarification_count":%s,"source_tagged_count":%s}\n' \
      "$non_clar_changed" "$clarification_count" "$source_tagged_count"
  else
    echo "OK: clarify guard passed"
    echo "  non_clarification_changed=$non_clar_changed"
    echo "  clarification_count=$clarification_count"
    echo "  source_tagged_count=$source_tagged_count"
  fi
}

require_file() {
  local path=$1
  local label=$2
  [[ -n "$path" ]] || emit_fail "$label path is empty"
  [[ -f "$path" ]] || emit_fail "$label not found: $path"
  [[ -s "$path" ]] || emit_fail "$label is empty: $path"
}

extract_non_clarification() {
  local path=$1
  awk '
    BEGIN { in_clar=0 }
    /^##[[:space:]]+Clarifications([[:space:]]|$)/ { in_clar=1; next }
    in_clar && /^##[[:space:]]+/ { in_clar=0 }
    !in_clar { print }
  ' "$path" | sed -E 's/[[:space:]]+$//'
}

extract_clarification_section() {
  local path=$1
  awk '
    BEGIN { in_clar=0 }
    /^##[[:space:]]+Clarifications([[:space:]]|$)/ { in_clar=1; next }
    in_clar && /^##[[:space:]]+/ { exit }
    in_clar { print }
  ' "$path" | sed -E 's/[[:space:]]+$//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --before)
      before_spec="${2:-}"
      shift 2
      ;;
    --after)
      after_spec="${2:-}"
      shift 2
      ;;
    --allow-non-clarification-change)
      allow_non_clarification_change=true
      shift
      ;;
    --min-clarifications)
      min_clarifications="${2:-}"
      shift 2
      ;;
    --json)
      json_mode=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      emit_fail "unknown argument: $1"
      ;;
  esac
done

require_file "$before_spec" "before spec"
require_file "$after_spec" "after spec"

if ! [[ "$min_clarifications" =~ ^[0-9]+$ ]]; then
  emit_fail "--min-clarifications must be a non-negative integer"
fi

if ! grep -Eq '^##[[:space:]]+Clarifications([[:space:]]|$)' "$after_spec"; then
  emit_fail "after spec missing '## Clarifications' section"
fi

before_non_clar="$(extract_non_clarification "$before_spec")"
after_non_clar="$(extract_non_clarification "$after_spec")"

non_clarification_changed=false
if [[ "$before_non_clar" != "$after_non_clar" ]]; then
  non_clarification_changed=true
fi

if [[ "$non_clarification_changed" == true ]] && ! $allow_non_clarification_change; then
  emit_fail "detected non-clarification content change; clarify should be append-only by default"
fi

clar_section="$(extract_clarification_section "$after_spec")"
if [[ -z "$clar_section" ]]; then
  emit_fail "clarifications section exists but has no content"
fi

clarification_count=$(printf '%s\n' "$clar_section" | grep -Ec '^[[:space:]]*-[[:space:]]*Q:' || true)
source_tagged_count=$(printf '%s\n' "$clar_section" | grep -Ec '^[[:space:]]*-[[:space:]]*Q:.*Source:[[:space:]]*\S+' || true)

if (( clarification_count < min_clarifications )); then
  emit_fail "clarification entry count ($clarification_count) is below required minimum ($min_clarifications)"
fi

if (( source_tagged_count < clarification_count )); then
  emit_fail "all clarification entries must include 'Source: <anchor>'"
fi

emit_ok "$non_clarification_changed" "$clarification_count" "$source_tagged_count"
