#!/usr/bin/env bash
set -euo pipefail

# create-release-packages.sh (workflow-local)
# Build Spec Kit template release archives for each supported AI assistant and script type.
# Usage: .github/workflows/scripts/create-release-packages.sh <version>
#   Version argument should include leading 'v'.
#   Optionally set AGENTS and/or SCRIPTS env vars to limit what gets built.
#     AGENTS  : space or comma separated subset of: claude gemini copilot cursor-agent qwen opencode windsurf codex kilocode auggie roo codebuddy qodercli amp shai tabnine kiro-cli agy bob droid vibe kimi trae pi iflow generic (default: all)
#     SCRIPTS : space or comma separated subset of: sh ps (default: both)
#   Examples:
#     AGENTS=claude SCRIPTS=sh $0 v0.2.0
#     AGENTS="copilot,gemini" $0 v0.2.0
#     SCRIPTS=ps $0 v0.2.0

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <version-with-v-prefix>" >&2
  exit 1
fi
NEW_VERSION="$1"
if [[ ! $NEW_VERSION =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Version must look like v0.0.0" >&2
  exit 1
fi

echo "Building release packages for $NEW_VERSION"

# Create and use .genreleases directory for all build artifacts
GENRELEASES_DIR="${GENRELEASES_DIR:-.genreleases}"
mkdir -p "$GENRELEASES_DIR"
rm -rf "$GENRELEASES_DIR"/* || true

SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(CDPATH="" cd "$SCRIPT_DIR/../../.." && pwd)"
source "$REPO_ROOT/scripts/bash/agent-registry.sh"
load_agent_registry

rewrite_paths() {
  sed -E \
    -e 's@(^|[[:space:]]|`|"|\(|\)|\{|\}|\[|\]|:|=|,)\./memory/@\1./.specify/memory/@g' \
    -e 's@(^|[[:space:]]|`|"|\(|\)|\{|\}|\[|\]|:|=|,)/memory/@\1.specify/memory/@g' \
    -e 's@(^|[[:space:]]|`|"|\(|\)|\{|\}|\[|\]|:|=|,)memory/@\1.specify/memory/@g' \
    -e 's@(^|[[:space:]]|`|"|\(|\)|\{|\}|\[|\]|:|=|,)\./scripts/@\1./.specify/scripts/@g' \
    -e 's@(^|[[:space:]]|`|"|\(|\)|\{|\}|\[|\]|:|=|,)/scripts/@\1.specify/scripts/@g' \
    -e 's@(^|[[:space:]]|`|"|\(|\)|\{|\}|\[|\]|:|=|,)scripts/@\1.specify/scripts/@g' \
    -e 's@(^|[[:space:]]|`|"|\(|\)|\{|\}|\[|\]|:|=|,)\./templates/@\1./.specify/templates/@g' \
    -e 's@(^|[[:space:]]|`|"|\(|\)|\{|\}|\[|\]|:|=|,)/templates/@\1.specify/templates/@g' \
    -e 's@(^|[[:space:]]|`|"|\(|\)|\{|\}|\[|\]|:|=|,)templates/@\1.specify/templates/@g'
}

command_template_files() {
  [[ -d templates/commands ]] || return 0
  find templates/commands -maxdepth 1 -type f -name '*.md' -print | LC_ALL=C sort
}

generate_commands() {
  local agent=$1 ext=$2 arg_format=$3 output_dir=$4 script_variant=$5
  mkdir -p "$output_dir"
  while IFS= read -r template; do
    [[ -f "$template" ]] || continue
    local name description script_command agent_script_command body frontmatter
    name=$(basename "$template" .md)

    # Normalize line endings
    file_content=$(tr -d '\r' < "$template")

    # Extract description from YAML frontmatter
    description=$(awk '/^description:/ {sub(/^description:[[:space:]]*/, ""); print; exit}' <<< "$file_content")
    body="$file_content"

    script_command=$(awk -v sv="$script_variant" '
      /^[[:space:]]*[a-zA-Z0-9_-]+:[[:space:]]*/ {
        if ($0 ~ "^[[:space:]]*" sv ":[[:space:]]*") {
          sub("^[[:space:]]*" sv ":[[:space:]]*", "")
          print
          exit
        }
      }
    ' <<< "$file_content")

    if [[ -z $script_command ]]; then
      echo "Warning: no script command found for $script_variant in $template" >&2
      script_command="(Missing script command for $script_variant)"
    fi

    agent_script_command=$(awk '
      /^agent_scripts:$/ { in_agent_scripts=1; next }
      in_agent_scripts && /^[[:space:]]*'"$script_variant"':[[:space:]]*/ {
        sub(/^[[:space:]]*'"$script_variant"':[[:space:]]*/, "")
        print
        exit
      }
      in_agent_scripts && /^[a-zA-Z]/ { in_agent_scripts=0 }
    ' <<< "$file_content")

    body=$(printf '%s\n' "$body" | sed "s|{SCRIPT}|${script_command}|g")
    if [[ -n $agent_script_command ]]; then
      body=$(printf '%s\n' "$body" | sed "s|{AGENT_SCRIPT}|${agent_script_command}|g")
    fi

    # Codex and Kimi skills strip source frontmatter script matrices after
    # placeholders are concretized; other agents keep the original frontmatter.
    if [[ $agent == "codex" || $agent == "kimi" ]]; then

      body=$(printf '%s\n' "$body" | awk '
        /^---$/ { print; if (++dash_count == 1) in_frontmatter=1; else in_frontmatter=0; next }
        in_frontmatter && /^scripts:$/ { skip_scripts=1; next }
        in_frontmatter && /^agent_scripts:$/ { skip_scripts=1; next }
        in_frontmatter && /^[a-zA-Z].*:/ && skip_scripts { skip_scripts=0 }
        in_frontmatter && skip_scripts && /^[[:space:]]/ { next }
        { print }
      ')
    fi

    # Apply other substitutions
    body=$(printf '%s\n' "$body" | sed "s/{ARGS}/$arg_format/g" | sed "s/__AGENT__/$agent/g" | rewrite_paths)

    case $ext in
      toml)
        body=$(printf '%s\n' "$body" | sed 's/\\/\\\\/g')
        { echo "description = \"$description\""; echo; echo "prompt = \"\"\""; echo "$body"; echo "\"\"\""; } > "$output_dir/speckit.$name.$ext" ;;
      md)
        if [[ $agent == "codex" ]]; then
          skill_name="speckit-$name"
          skill_dir="$output_dir/$skill_name"
          escaped_description=$(printf '%s' "$description" | sed 's/"/\\"/g')
          skill_body=$(printf '%s\n' "$body" | awk '
            state == 0 {
              if ($0 == "") { next }
              if ($0 == "---") { state = 1; next }
              state = 2
            }
            state == 1 {
              if ($0 == "---") { state = 2; next }
              next
            }
            state == 2 { print }
          ')
          mkdir -p "$skill_dir"
          {
            echo "---"
            echo "name: $skill_name"
            echo "description: \"$escaped_description\""
            echo "---"
            echo
            printf '%s\n' "$skill_body"
          } > "$skill_dir/SKILL.md"
        else
          echo "$body" > "$output_dir/speckit.$name.$ext"
        fi ;;
      agent.md)
        echo "$body" > "$output_dir/speckit.$name.$ext" ;;
    esac
  done < <(command_template_files)
}

generate_copilot_prompts() {
  local agents_dir=$1 prompts_dir=$2
  mkdir -p "$prompts_dir"

  # Generate a .prompt.md file for each .agent.md file
  for agent_file in "$agents_dir"/speckit.*.agent.md; do
    [[ -f "$agent_file" ]] || continue

    local basename=$(basename "$agent_file" .agent.md)
    local prompt_file="$prompts_dir/${basename}.prompt.md"

    cat > "$prompt_file" <<EOF
---
agent: ${basename}
---
EOF
  done
}

# Create Kimi Code skills in .kimi/skills/<name>/SKILL.md format.
# Kimi CLI discovers skills as directories containing a SKILL.md file,
# invoked with /skill:<name> (e.g. /skill:speckit-specify).
create_kimi_skills() {
  local skills_dir="$1"
  local script_variant="$2"

  while IFS= read -r template; do
    [[ -f "$template" ]] || continue
    local name
    name=$(basename "$template" .md)
    local skill_name="speckit-${name}"
    local skill_dir="${skills_dir}/${skill_name}"
    mkdir -p "$skill_dir"

    local file_content
    file_content=$(tr -d '\r' < "$template")

    # Extract description from frontmatter
    local description
    description=$(printf '%s\n' "$file_content" | awk '/^description:/ {sub(/^description:[[:space:]]*/, ""); print; exit}')
    [[ -z "$description" ]] && description="Spec Kit: ${name} workflow"

    # Extract script command
    local script_command
    script_command=$(printf '%s\n' "$file_content" | awk -v sv="$script_variant" '/^[[:space:]]*'"$script_variant"':[[:space:]]*/ {sub(/^[[:space:]]*'"$script_variant"':[[:space:]]*/, ""); print; exit}')
    [[ -z "$script_command" ]] && script_command="(Missing script command for $script_variant)"

    # Extract agent_script command from frontmatter if present
    local agent_script_command
    agent_script_command=$(printf '%s\n' "$file_content" | awk '
      /^agent_scripts:$/ { in_agent_scripts=1; next }
      in_agent_scripts && /^[[:space:]]*'"$script_variant"':[[:space:]]*/ {
        sub(/^[[:space:]]*'"$script_variant"':[[:space:]]*/, "")
        print
        exit
      }
      in_agent_scripts && /^[a-zA-Z]/ { in_agent_scripts=0 }
    ')

    # Build body: replace placeholders, strip scripts sections, rewrite paths
    local body
    body=$(printf '%s\n' "$file_content" | sed "s|{SCRIPT}|${script_command}|g")
    if [[ -n $agent_script_command ]]; then
      body=$(printf '%s\n' "$body" | sed "s|{AGENT_SCRIPT}|${agent_script_command}|g")
    fi
    body=$(printf '%s\n' "$body" | awk '
      /^---$/ { print; if (++dash_count == 1) in_frontmatter=1; else in_frontmatter=0; next }
      in_frontmatter && /^scripts:$/ { skip_scripts=1; next }
      in_frontmatter && /^agent_scripts:$/ { skip_scripts=1; next }
      in_frontmatter && /^[a-zA-Z].*:/ && skip_scripts { skip_scripts=0 }
      in_frontmatter && skip_scripts && /^[[:space:]]/ { next }
      { print }
    ')
    body=$(printf '%s\n' "$body" | sed 's/{ARGS}/\$ARGUMENTS/g' | sed 's/__AGENT__/kimi/g' | rewrite_paths)

    # Strip existing frontmatter and prepend Kimi frontmatter
    local template_body
    template_body=$(printf '%s\n' "$body" | awk '/^---/{p++; if(p==2){found=1; next}} found')

    {
      printf -- '---\n'
      printf 'name: "%s"\n' "$skill_name"
      printf 'description: "%s"\n' "$description"
      printf -- '---\n\n'
      printf '%s\n' "$template_body"
    } > "$skill_dir/SKILL.md"
  done < <(command_template_files)
}

build_variant() {
  local agent=$1 script=$2
  local base_dir="$GENRELEASES_DIR/sdd-${agent}-package-${script}"
  echo "Building $agent ($script) package..."
  mkdir -p "$base_dir"

  # Copy base structure but filter scripts by variant
  SPEC_DIR="$base_dir/.specify"
  mkdir -p "$SPEC_DIR"

  [[ -d memory ]] && { cp -r memory "$SPEC_DIR/"; echo "Copied memory -> .specify"; }

  # Only copy the relevant script variant directory
  if [[ -d scripts ]]; then
    mkdir -p "$SPEC_DIR/scripts"
    case $script in
      sh)
        [[ -d scripts/bash ]] && { cp -r scripts/bash "$SPEC_DIR/scripts/"; echo "Copied scripts/bash -> .specify/scripts"; }
        find scripts -maxdepth 1 -type f -exec cp {} "$SPEC_DIR/scripts/" \; 2>/dev/null || true
        ;;
      ps)
        [[ -d scripts/powershell ]] && { cp -r scripts/powershell "$SPEC_DIR/scripts/"; echo "Copied scripts/powershell -> .specify/scripts"; }
        find scripts -maxdepth 1 -type f -exec cp {} "$SPEC_DIR/scripts/" \; 2>/dev/null || true
        ;;
    esac
  fi

  if [[ -d templates ]]; then
    mkdir -p "$SPEC_DIR/templates"
    if [[ $(agent_registry_field "$agent" "exclude_agent_templates") == "1" ]]; then
      while IFS= read -r -d '' template_file; do
        rel_path="${template_file#templates/}"
        target_path="$SPEC_DIR/templates/$rel_path"
        mkdir -p "$(dirname "$target_path")"
        cp "$template_file" "$target_path"
      done < <(
        find templates -type f \
          -not -path "templates/commands/*" \
          -not -path "templates/fork-commands/*" \
          -not -path "templates/agents/*" \
          -not -name "vscode-settings.json" \
          -print0
      )
    else
      while IFS= read -r -d '' template_file; do
        rel_path="${template_file#templates/}"
        target_path="$SPEC_DIR/templates/$rel_path"
        mkdir -p "$(dirname "$target_path")"
        cp "$template_file" "$target_path"
      done < <(
        find templates -type f \
          -not -path "templates/commands/*" \
          -not -path "templates/fork-commands/*" \
          -not -name "vscode-settings.json" \
          -print0
      )
    fi
    echo "Copied templates -> .specify/templates"
  fi
  
  # NOTE: We substitute {ARGS} internally. Outward tokens differ intentionally:
  #   * Markdown/prompt (claude, copilot, cursor-agent, opencode): $ARGUMENTS
  #   * TOML (gemini, qwen): {{args}}
  # This keeps formats readable without extra abstraction.
  local command_dir
  command_dir=$(agent_registry_field "$agent" "command_dir")
  local args_value
  args_value=$(agent_registry_args_value "$(agent_registry_field "$agent" "args_token")")
  local strategy
  strategy=$(agent_registry_field "$agent" "package_strategy")
  local output_dir="$base_dir/$command_dir"
  mkdir -p "$output_dir"

  case "$strategy" in
    standard_commands|copilot_agent|codex_skill_tree)
      local command_ext
      local agent_extension
      agent_extension=$(agent_registry_field "$agent" "extension")
      case "$agent_extension" in
        .md) command_ext="md" ;;
        .toml) command_ext="toml" ;;
        .agent.md) command_ext="agent.md" ;;
        /SKILL.md) command_ext="md" ;;
        *)
          echo "Unsupported command extension '$agent_extension' for agent '$agent'" >&2
          exit 1
          ;;
      esac
      generate_commands "$agent" "$command_ext" "$args_value" "$output_dir" "$script"
      ;;
    kimi_skill_tree)
      create_kimi_skills "$output_dir" "$script"
      ;;
    *)
      echo "Unsupported packaging strategy '$strategy' for agent '$agent'" >&2
      exit 1
      ;;
  esac

  if [[ "$strategy" == "copilot_agent" ]]; then
    generate_copilot_prompts "$output_dir" "$base_dir/.github/prompts"
  fi

  if [[ $(agent_registry_field "$agent" "copy_vscode_settings") == "1" ]]; then
    mkdir -p "$base_dir/.vscode"
    [[ -f templates/vscode-settings.json ]] && cp templates/vscode-settings.json "$base_dir/.vscode/settings.json"
  fi

  local root_copy_source root_copy_dest
  root_copy_source=$(agent_registry_field "$agent" "root_copy_source")
  root_copy_dest=$(agent_registry_field "$agent" "root_copy_dest")
  if [[ -n $root_copy_source && -n $root_copy_dest ]]; then
    [[ -f $root_copy_source ]] && cp "$root_copy_source" "$base_dir/$root_copy_dest"
  fi

  local copy_agent_templates_to
  copy_agent_templates_to=$(agent_registry_field "$agent" "copy_agent_templates_to")
  if [[ -n $copy_agent_templates_to && -d templates/agents ]]; then
    mkdir -p "$base_dir/$copy_agent_templates_to"
    for agent_file in templates/agents/*.md; do
      [[ -f "$agent_file" ]] || continue
      cp "$agent_file" "$base_dir/$copy_agent_templates_to/"
    done
    echo "Copied agents -> $copy_agent_templates_to"
  fi

  local legacy_mirror_dir
  legacy_mirror_dir=$(agent_registry_field "$agent" "legacy_mirror_dir")
  if [[ -n $legacy_mirror_dir ]]; then
    mkdir -p "$base_dir/$legacy_mirror_dir"
    cp -R "$output_dir/." "$base_dir/$legacy_mirror_dir/"
  fi

  # Generate .version and .file-hashes for update tracking
  echo "$NEW_VERSION" > "$SPEC_DIR/.version"
  ( cd "$base_dir" && find . -type f ! -name '.file-hashes' -print0 | sort -z | xargs -0 shasum -a 256 > .specify/.file-hashes )

  ( cd "$base_dir" && zip -r "../spec-kit-template-${agent}-${script}-${NEW_VERSION}.zip" . )
  echo "Created $GENRELEASES_DIR/spec-kit-template-${agent}-${script}-${NEW_VERSION}.zip"
}

# Determine agent list
ALL_AGENTS=("${AGENT_REGISTRY_ORDER[@]}")
ALL_SCRIPTS=(sh ps)

norm_list() {
  tr ',\n' '  ' | awk '{for(i=1;i<=NF;i++){if(!seen[$i]++){printf((out?"\n":"") $i);out=1}}}END{printf("\n")}'
}

validate_subset() {
  local type=$1
  shift
  local allowed=()
  local items=()
  local invalid=0
  local in_items=0
  local token

  for token in "$@"; do
    if [[ $in_items -eq 0 && $token == "--" ]]; then
      in_items=1
      continue
    fi
    if [[ $in_items -eq 0 ]]; then
      allowed+=("$token")
    else
      items+=("$token")
    fi
  done

  for it in "${items[@]}"; do
    local found=0
    for a in "${allowed[@]}"; do [[ $it == "$a" ]] && { found=1; break; }; done
    if [[ $found -eq 0 ]]; then
      echo "Error: unknown $type '$it' (allowed: ${allowed[*]})" >&2
      invalid=1
    fi
  done
  return $invalid
}

if [[ -n ${AGENTS:-} ]]; then
  AGENT_LIST=()
  while IFS= read -r agent; do
    [[ -n $agent ]] || continue
    AGENT_LIST+=("$agent")
  done < <(printf '%s' "$AGENTS" | norm_list)
  validate_subset agent "${ALL_AGENTS[@]}" -- "${AGENT_LIST[@]}" || exit 1
else
  AGENT_LIST=("${ALL_AGENTS[@]}")
fi

if [[ -n ${SCRIPTS:-} ]]; then
  SCRIPT_LIST=()
  while IFS= read -r script; do
    [[ -n $script ]] || continue
    SCRIPT_LIST+=("$script")
  done < <(printf '%s' "$SCRIPTS" | norm_list)
  validate_subset script "${ALL_SCRIPTS[@]}" -- "${SCRIPT_LIST[@]}" || exit 1
else
  SCRIPT_LIST=("${ALL_SCRIPTS[@]}")
fi

echo "Agents: ${AGENT_LIST[*]}"
echo "Scripts: ${SCRIPT_LIST[*]}"

for agent in "${AGENT_LIST[@]}"; do
  for script in "${SCRIPT_LIST[@]}"; do
    build_variant "$agent" "$script"
  done
done

echo "Archives in $GENRELEASES_DIR:"
ls -1 "$GENRELEASES_DIR"/spec-kit-template-*-"${NEW_VERSION}".zip
