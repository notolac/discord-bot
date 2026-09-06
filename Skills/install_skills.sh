#!/usr/bin/env bash
# Interactive installer for repo Agent Skills under Skills/.
# Symlinks (or copies) each skill into IDE-specific discovery paths.
# OpenCode installs matching command wrappers from commands/opencode/.
#
# Usage:
#   ./install_skills.sh                    Interactive wizard
#   ./install_skills.sh --auto             All skills, detected IDE, project, symlink
#   ./install_skills.sh --auto --skill discord-docs
#   ./install_skills.sh --sync             Install only new/missing skills (reuse prior IDE prefs)
#   ./install_skills.sh --list             IDE path reference
#   ./install_skills.sh --skills           List skills in this folder
#   ./install_skills.sh --uninstall        Remove installed skills (interactive pick)
#   ./install_skills.sh --uninstall --all  Remove all repo skills

set -euo pipefail

readonly SKILLS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# OpenCode slash-command prefix: /discord.docs, /discord.<skill>.<action>
readonly COMMAND_PREFIX="discord"

if repo_root="$(git -C "${SKILLS_ROOT}" rev-parse --show-toplevel 2>/dev/null)"; then
  readonly REPO_ROOT="${repo_root}"
else
  readonly REPO_ROOT="$(cd "${SKILLS_ROOT}/.." && pwd)"
fi

# Active skill context (set via activate_skill before per-skill operations).
SKILL_NAME=""
SKILL_DIR=""
MANIFEST_FILE=""
OPENCODE_COMMAND_REMOVED=0

# --- styling (disabled when not a TTY) ---
if [[ -t 1 ]]; then
  BOLD=$'\033[1m'
  DIM=$'\033[2m'
  GREEN=$'\033[32m'
  YELLOW=$'\033[33m'
  RED=$'\033[31m'
  CYAN=$'\033[36m'
  RESET=$'\033[0m'
else
  BOLD="" DIM="" GREEN="" YELLOW="" RED="" CYAN="" RESET=""
fi

info()  { printf "%s%s%s\n" "${CYAN}" "$*" "${RESET}"; }
ok()    { printf "%s%s%s\n" "${GREEN}" "$*" "${RESET}"; }
warn()  { printf "%s%s%s\n" "${YELLOW}" "$*" "${RESET}" >&2; }
err()   { printf "%s%s%s\n" "${RED}" "$*" "${RESET}" >&2; }
die()   { err "$*"; exit 1; }
ui()    { printf '%b\n' "$*" >&2; }
ask() {
  local _prompt="$1"
  local _var="$2"
  printf '%b' "${_prompt}" >&2
  if [[ -t 0 ]]; then
    IFS= read -r "${_var}" < /dev/tty 2>/dev/null || IFS= read -r "${_var}"
  else
    IFS= read -r "${_var}" || printf -v "${_var}" ''
  fi
}

usage() {
  cat <<EOF
${BOLD}discord-bot Agent Skills installer${RESET}

Installs skills from: ${SKILLS_ROOT}
Repo root: ${REPO_ROOT}

Skills are discovered automatically: any Skills/<name>/SKILL.md folder counts.
No allowlist — add a new skill folder and re-run --sync / --auto.

Usage:
  $(basename "$0")                         Interactive wizard
  $(basename "$0") --auto                  Install all skills (detected IDE, project, symlink)
  $(basename "$0") --auto --skill NAME      Install one skill (repeatable)
  $(basename "$0") --sync                  Install new/missing skills (reuse prior IDE prefs)
  $(basename "$0") --skills                 List available skills in Skills/
  $(basename "$0") --list                   Print IDE install paths (per skill)
  $(basename "$0") --uninstall              Uninstall (interactive skill pick)
  $(basename "$0") --uninstall --all        Uninstall every repo skill
  $(basename "$0") --uninstall --skill NAME Uninstall one skill
  $(basename "$0") --uninstall --dry-run    Preview uninstall actions
  $(basename "$0") --help                   Show this help

After install, reload your IDE. OpenCode commands use the `${COMMAND_PREFIX}.*` prefix.
EOF
}

activate_skill() {
  local slug="$1"
  SKILL_NAME="${slug}"
  SKILL_DIR="${SKILLS_ROOT}/${slug}"
  MANIFEST_FILE="${SKILL_DIR}/.install-manifest"
}

# Auto-discover every Skills/<slug>/SKILL.md (no hardcoded skill list).
discover_skills() {
  local dir slug
  (
    shopt -s nullglob
    for dir in "${SKILLS_ROOT}"/*/; do
      [[ -d "${dir}" ]] || continue
      slug="$(basename "${dir%/}")"
      [[ "${slug}" != .* ]] || continue
      [[ -f "${dir}SKILL.md" ]] || continue
      printf '%s\n' "${slug}"
    done
  ) | sort -u
}

validate_skills_root() {
  local count=0
  local _skill
  while IFS= read -r _skill; do
    [[ -n "${_skill}" ]] && count=$((count + 1))
  done < <(discover_skills)
  if [[ "${count}" -eq 0 ]]; then
    err "No skills found in ${SKILLS_ROOT} (expected Skills/<name>/SKILL.md)."
    exit 1
  fi
}

validate_skill_dir() {
  if [[ ! -f "${SKILL_DIR}/SKILL.md" ]]; then
    err "Missing ${SKILL_DIR}/SKILL.md"
    exit 1
  fi
}

skill_blurb() {
  local slug="$1"
  local md="${SKILLS_ROOT}/${slug}/SKILL.md"
  local blurb=""
  blurb="$(awk '
    BEGIN { in_front=0 }
    /^---$/ { in_front++; next }
    in_front == 1 && /^description:[[:space:]]*/ {
      line = substr($0, index($0, ":") + 1)
      sub(/^[[:space:]]*/, "", line)
      if (line ~ /^[>|][-+]?$/) { multi=1; next }
      print line
      exit
    }
    in_front == 1 && multi == 1 {
      if ($0 ~ /^[[:space:]]*$/) exit
      gsub(/^[[:space:]]+/, "", $0)
      print $0
      exit
    }
  ' "${md}" 2>/dev/null || true)"
  if [[ -n "${blurb}" ]]; then
    printf '%.78s' "${blurb}"
  else
    printf 'Agent skill %s' "${slug}"
  fi
}

# Returns install target paths for an IDE key: project|user
ide_targets() {
  local ide="$1"
  local scope="$2"
  case "${ide}:${scope}" in
    cursor:project)     echo "${REPO_ROOT}/.cursor/skills/${SKILL_NAME}" ;;
    cursor:user)        echo "${HOME}/.cursor/skills/${SKILL_NAME}" ;;
    copilot:project)    echo "${REPO_ROOT}/.github/skills/${SKILL_NAME}" ;;
    copilot:user)       echo "${HOME}/.copilot/skills/${SKILL_NAME}" ;;
    opencode:project)   echo "${REPO_ROOT}/.opencode/skills/${SKILL_NAME}" ;;
    opencode:user)      echo "${HOME}/.config/opencode/skills/${SKILL_NAME}" ;;
    claude:project)     echo "${REPO_ROOT}/.claude/skills/${SKILL_NAME}" ;;
    claude:user)        echo "${HOME}/.claude/skills/${SKILL_NAME}" ;;
    codex:project)      echo "${REPO_ROOT}/.agents/skills/${SKILL_NAME}" ;;
    codex:user)         echo "${HOME}/.agents/skills/${SKILL_NAME}" ;;
    agents:project)     echo "${REPO_ROOT}/.agents/skills/${SKILL_NAME}" ;;
    agents:user)        echo "${HOME}/.agents/skills/${SKILL_NAME}" ;;
    *)                  return 1 ;;
  esac
}

# OpenCode command files live beside each skill so command definitions remain
# portable with their underlying skill. Command filename becomes command name.
opencode_command_source_dir() {
  printf '%s/commands/opencode' "${SKILL_DIR}"
}

opencode_command_namespace() {
  case "${SKILL_NAME}" in
    discord-docs) printf 'docs' ;;
    admin-helper) printf 'admin' ;;
    *)            printf '%s' "${SKILL_NAME}" ;;
  esac
}

opencode_command_targets() {
  local scope="$1"
  local source command_name namespace
  local source_dir
  local nullglob_was_set=0
  source_dir="$(opencode_command_source_dir)"
  [[ -d "${source_dir}" ]] || return 0
  namespace="$(opencode_command_namespace)"

  shopt -q nullglob && nullglob_was_set=1
  shopt -s nullglob
  for source in "${source_dir}"/*.md; do
    command_name="$(basename "${source}" .md)"
    if [[ "${command_name}" == "default" ]]; then
      command_name="${COMMAND_PREFIX}.${namespace}"
    else
      command_name="${COMMAND_PREFIX}.${namespace}.${command_name}"
    fi

    case "${scope}" in
      project) printf '%s\t%s\n' "${source}" "${REPO_ROOT}/.opencode/commands/${command_name}.md" ;;
      user)    printf '%s\t%s\n' "${source}" "${HOME}/.config/opencode/commands/${command_name}.md" ;;
      *)       return 1 ;;
    esac
  done
  if [[ "${nullglob_was_set}" -eq 0 ]]; then
    shopt -u nullglob
  fi
}

ide_label() {
  case "$1" in
    cursor)   echo "Cursor" ;;
    copilot)  echo "VS Code / GitHub Copilot" ;;
    opencode) echo "OpenCode" ;;
    claude)   echo "Claude Code" ;;
    codex)    echo "OpenAI Codex" ;;
    agents)   echo "Universal (.agents/skills)" ;;
    *)        echo "$1" ;;
  esac
}

ide_docs_url() {
  case "$1" in
    cursor)   echo "https://cursor.com/docs/context/skills" ;;
    copilot)  echo "https://code.visualstudio.com/docs/copilot/customization/agent-skills" ;;
    opencode) echo "https://opencode.ai/docs/skills/" ;;
    claude)   echo "https://code.claude.com/docs/en/skills" ;;
    codex)    echo "https://developers.openai.com/codex/skills" ;;
    agents)   echo "https://agentskills.io" ;;
    *)        echo "" ;;
  esac
}

display_path() {
  local path="$1"
  local rel
  if [[ "${path}" == "${REPO_ROOT}"/* || "${path}" == "${REPO_ROOT}" ]]; then
    rel="${path#"${REPO_ROOT}"}"
    rel="${rel#/}"
    if [[ -n "${rel}" ]]; then
      printf './%s' "${rel}"
    else
      printf '.'
    fi
  elif [[ "${path}" == "${HOME}/"* ]]; then
    printf '~/%s' "${path#"${HOME}/"}"
  else
    printf '%s' "${path}"
  fi
}

canonical_path() {
  local path="$1"
  if [[ -z "${path}" || ! -e "${path}" && ! -L "${path}" ]]; then
    return 1
  fi
  readlink -f "${path}" 2>/dev/null || realpath "${path}" 2>/dev/null || echo "${path}"
}

is_our_skill_install() {
  local target="$1"
  local resolved skill_md

  if [[ -L "${target}" ]]; then
    resolved="$(canonical_path "${target}" || readlink "${target}")"
    [[ "${resolved}" == "${SKILL_DIR}" ]]
    return
  fi

  if [[ ! -d "${target}" ]]; then
    return 1
  fi

  skill_md="${target}/SKILL.md"
  [[ -f "${skill_md}" ]] && grep -Eq "^name:[[:space:]]*${SKILL_NAME}[[:space:]]*$" "${skill_md}"
}

is_our_opencode_command_install() {
  local source="$1"
  local target="$2"
  local resolved

  if [[ -L "${target}" ]]; then
    resolved="$(canonical_path "${target}" || readlink "${target}")"
    [[ "${resolved}" == "${source}" ]]
    return
  fi

  [[ -f "${target}" ]] && cmp -s "${source}" "${target}"
}

install_status_label() {
  local target="$1"
  if is_our_skill_install "${target}"; then
    printf 'already installed'
  elif [[ -e "${target}" || -L "${target}" ]]; then
    printf 'path occupied (not this skill)'
  else
    printf 'not installed'
  fi
}

# True if skill is linked/copied into any known IDE discovery path.
skill_is_installed_anywhere() {
  local slug="$1"
  local scope ide target
  local saved_name="${SKILL_NAME}" saved_dir="${SKILL_DIR}" saved_manifest="${MANIFEST_FILE}"

  activate_skill "${slug}"
  for scope in project user; do
    for ide in cursor copilot opencode claude codex agents; do
      target="$(ide_targets "${ide}" "${scope}")" || continue
      if is_our_skill_install "${target}"; then
        SKILL_NAME="${saved_name}"
        SKILL_DIR="${saved_dir}"
        MANIFEST_FILE="${saved_manifest}"
        return 0
      fi
    done
  done

  SKILL_NAME="${saved_name}"
  SKILL_DIR="${saved_dir}"
  MANIFEST_FILE="${saved_manifest}"
  return 1
}

# Infer prior install prefs from any Skills/*/.install-manifest.
# Prints unique lines: scope<TAB>method<TAB>ide
infer_install_prefs() {
  local manifest target method scope ide
  local -a manifests=()
  local nullglob_was_set=0

  shopt -q nullglob && nullglob_was_set=1
  shopt -s nullglob
  manifests=("${SKILLS_ROOT}"/*/.install-manifest)
  if [[ "${nullglob_was_set}" -eq 0 ]]; then
    shopt -u nullglob
  fi

  if ((${#manifests[@]} == 0)); then
    return 1
  fi

  for manifest in "${manifests[@]}"; do
    [[ -f "${manifest}" ]] || continue
    while IFS=$'\t' read -r target method scope ide _; do
      [[ -n "${target}" && -n "${method}" && -n "${scope}" && -n "${ide}" ]] || continue
       [[ "${ide}" == "codex-home" || "${ide}" == "opencode-command" ]] && continue
      printf '%s\t%s\t%s\n' "${scope}" "${method}" "${ide}"
    done < "${manifest}"
  done | awk -F'\t' '!seen[$0]++'
}

# Skills present under Skills/ but missing from at least one inferred target.
list_missing_skills() {
  local -a prefs=()
  local -a skills=()
  local slug line scope method ide target needs

  while IFS= read -r line; do
    [[ -n "${line}" ]] && prefs+=("${line}")
  done < <(infer_install_prefs || true)

  while IFS= read -r slug; do
    [[ -n "${slug}" ]] && skills+=("${slug}")
  done < <(discover_skills)

  if ((${#prefs[@]} == 0)); then
    for slug in "${skills[@]}"; do
      if ! skill_is_installed_anywhere "${slug}"; then
        printf '%s\n' "${slug}"
      fi
    done
    return 0
  fi

  for slug in "${skills[@]}"; do
    needs=0
    activate_skill "${slug}"
    for line in "${prefs[@]}"; do
      IFS=$'\t' read -r scope method ide <<< "${line}"
      target="$(ide_targets "${ide}" "${scope}")" || continue
      if ! is_our_skill_install "${target}"; then
        needs=1
        break
      fi
    done
    [[ "${needs}" -eq 1 ]] && printf '%s\n' "${slug}"
  done
}

resolve_existing() {
  local target="$1"
  if [[ -L "${target}" ]]; then
    echo "symlink:$(canonical_path "${target}" 2>/dev/null || readlink "${target}")"
  elif [[ -d "${target}" ]]; then
    echo "directory"
  elif [[ -e "${target}" ]]; then
    echo "file"
  else
    echo "missing"
  fi
}

collect_install_targets() {
  local scope ide target codex_home
  local -a targets=()

  for scope in project user; do
    for ide in cursor copilot opencode claude codex agents; do
      target="$(ide_targets "${ide}" "${scope}")"
      targets+=("${target}")
      if [[ "${scope}" == "user" ]]; then
        codex_home="${CODEX_HOME:-${HOME}/.codex}/skills/${SKILL_NAME}"
        targets+=("${codex_home}")
      fi
    done
  done

  local root candidate
  for root in \
    "${REPO_ROOT}/.cursor" "${REPO_ROOT}/.github" "${REPO_ROOT}/.opencode" \
    "${REPO_ROOT}/.claude" "${REPO_ROOT}/.agents" \
    "${HOME}/.cursor" "${HOME}/.copilot" "${HOME}/.config/opencode" \
    "${HOME}/.claude" "${HOME}/.agents" "${CODEX_HOME:-${HOME}/.codex}"
  do
    [[ -d "${root}" ]] || continue
    while IFS= read -r -d '' candidate; do
      targets+=("${candidate}")
    done < <(find "${root}" -mindepth 1 -maxdepth 4 -name "${SKILL_NAME}" \
      \( -type l -o -type d \) -print0 2>/dev/null)
  done

  printf '%s\n' "${targets[@]}" | awk '!seen[$0]++ && $0 != ""'
}

parents_to_create() {
  local target="$1"
  local -a created=()
  local dir next

  dir="$(dirname "${target}")"
  while [[ -n "${dir}" && "${dir}" != "/" ]]; do
    [[ -d "${dir}" ]] || created+=("${dir}")
    next="${dir%/*}"
    [[ "${next}" == "${dir}" ]] && break
    dir="${next}"
  done

  if ((${#created[@]} > 0)); then
    printf '%s\n' "${created[@]}"
  fi
}

parents_join() {
  local IFS='|'
  echo "$*"
}

manifest_upsert() {
  local target="$1"
  local method="$2"
  local scope="$3"
  local ide="$4"
  local parents="$5"
  local tmp

  tmp="$(mktemp)"
  if [[ -f "${MANIFEST_FILE}" ]]; then
    grep -v "^$(printf '%s' "${target}" | sed 's/[[\.*^$()+?{|]/\\&/g')"$'\t' "${MANIFEST_FILE}" > "${tmp}" || true
  fi
  printf '%s\t%s\t%s\t%s\t%s\n' \
    "${target}" "${method}" "${scope}" "${ide}" "${parents}" >> "${tmp}"
  mv "${tmp}" "${MANIFEST_FILE}"
}

manifest_remove_target() {
  local target="$1"
  local tmp

  [[ -f "${MANIFEST_FILE}" ]] || return 0
  tmp="$(mktemp)"
  grep -v "^$(printf '%s' "${target}" | sed 's/[[\.*^$()+?{|]/\\&/g')"$'\t' "${MANIFEST_FILE}" > "${tmp}" || true
  if [[ -s "${tmp}" ]]; then
    mv "${tmp}" "${MANIFEST_FILE}"
  else
    rm -f "${tmp}" "${MANIFEST_FILE}"
  fi
}

manifest_parents_for() {
  local target="$1"
  local line parents

  [[ -f "${MANIFEST_FILE}" ]] || return 0
  line="$(grep "^$(printf '%s' "${target}" | sed 's/[[\.*^$()+?{|]/\\&/g')"$'\t' "${MANIFEST_FILE}" | head -n1 || true)"
  [[ -n "${line}" ]] || return 0
  IFS=$'\t' read -r _ _ _ _ parents <<< "${line}"
  [[ -n "${parents}" ]] || return 0

  local old_ifs="${IFS}" dir
  IFS='|' read -ra dirs <<< "${parents}"
  IFS="${old_ifs}"
  for dir in "${dirs[@]}"; do
    [[ -n "${dir}" ]] && printf '%s\n' "${dir}"
  done
}

dir_depth() {
  local path="$1"
  printf '%s' "${path}" | tr -cd '/' | wc -c
}

prune_created_parents() {
  local dry_run="$1"
  shift
  local -a parents=("$@")
  local -a sorted=()
  local dir depth

  if ((${#parents[@]} == 0)); then
    return 0
  fi

  while IFS= read -r line; do
    sorted+=("${line}")
  done < <(
    for dir in "${parents[@]}"; do
      depth="$(dir_depth "${dir}")"
      printf '%03d\t%s\n' "${depth}" "${dir}"
    done | sort -rn | cut -f2-
  )

  for dir in "${sorted[@]}"; do
    [[ -d "${dir}" ]] || continue
    if [[ -n "$(ls -A "${dir}" 2>/dev/null)" ]]; then
      info "  kept ${dir} (contains other content)"
      continue
    fi
    if [[ "${dry_run}" == "1" ]]; then
      ok "  would remove created dir: ${dir}"
    elif rmdir "${dir}" 2>/dev/null; then
      ok "  removed created dir: ${dir}"
    else
      warn "  could not remove ${dir} (not empty or permission denied)"
    fi
  done
}

remove_backups_near() {
  local target="$1"
  local dry_run="${2:-0}"
  local parent="${1%/*}"
  local backup

  shopt -s nullglob
  for backup in "${parent}/${SKILL_NAME}.bak."*; do
    if [[ "${dry_run}" == "1" ]]; then
      ok "  would remove backup: ${backup}"
    else
      rm -rf "${backup}"
      ok "  removed backup: ${backup}"
    fi
  done
  shopt -u nullglob
}

remove_one() {
  local target="$1"
  local dry_run="${2:-0}"

  if [[ ! -e "${target}" && ! -L "${target}" ]]; then
    remove_backups_near "${target}" "${dry_run}"
    return 0
  fi

  if ! is_our_skill_install "${target}"; then
    warn "  skipped (not our install): ${target}"
    return 0
  fi

  if [[ "${dry_run}" == "1" ]]; then
    ok "  would remove: ${target}"
  elif [[ -L "${target}" ]]; then
    rm -f "${target}"
    ok "  removed symlink: ${target}"
  elif [[ -d "${target}" ]]; then
    rm -rf "${target}"
    ok "  removed directory: ${target}"
  else
    rm -f "${target}"
    ok "  removed file: ${target}"
  fi

  remove_backups_near "${target}" "${dry_run}"
  if [[ "${dry_run}" != "1" ]]; then
    manifest_remove_target "${target}"
  fi
}

install_one() {
  local target="$1"
  local method="$2"
  local scope="${3:-unknown}"
  local ide="${4:-unknown}"
  local state
  local -a parents_created=()
  local parents_joined

  while IFS= read -r dir; do
    [[ -n "${dir}" ]] && parents_created+=("${dir}")
  done < <(parents_to_create "${target}")

  if ((${#parents_created[@]} > 0)); then
    parents_joined="$(parents_join "${parents_created[@]}")"
  else
    parents_joined=""
  fi

  state="$(resolve_existing "${target}")"
  mkdir -p "$(dirname "${target}")"

  case "${state}" in
    missing)
      ;;
    symlink:*)
      local current="${state#symlink:}"
      if [[ "${current}" == "${SKILL_DIR}" ]]; then
        ok "  already linked: ${target}"
        manifest_upsert "${target}" "${method}" "${scope}" "${ide}" "${parents_joined}"
        return 0
      fi
      warn "  replacing symlink ${target} (was → ${current})"
      rm -f "${target}"
      ;;
    directory|file)
      warn "  ${target} exists as ${state}; moving to ${target}.bak.$(date +%s)"
      mv "${target}" "${target}.bak.$(date +%s)"
      ;;
  esac

  if [[ "${method}" == "symlink" ]]; then
    ln -s "${SKILL_DIR}" "${target}"
    ok "  symlink: ${target} → ${SKILL_DIR}"
  else
    cp -a "${SKILL_DIR}" "${target}"
    ok "  copied:  ${target}"
  fi

  manifest_upsert "${target}" "${method}" "${scope}" "${ide}" "${parents_joined}"
}

install_opencode_commands() {
  local scope="$1"
  local method="$2"
  local source target state command_name
  local -a parents_created=()
  local parents_joined

  while IFS=$'\t' read -r source target; do
    [[ -n "${source}" && -n "${target}" ]] || continue
    command_name="$(basename "${target}" .md)"
    parents_created=()
    while IFS= read -r dir; do
      [[ -n "${dir}" ]] && parents_created+=("${dir}")
    done < <(parents_to_create "${target}")
    if ((${#parents_created[@]} > 0)); then
      parents_joined="$(parents_join "${parents_created[@]}")"
    else
      parents_joined=""
    fi

    state="$(resolve_existing "${target}")"
    mkdir -p "$(dirname "${target}")"
    case "${state}" in
      missing)
        ;;
      symlink:*)
        if is_our_opencode_command_install "${source}" "${target}"; then
          ok "  command already linked: ${target}"
          manifest_upsert "${target}" "${method}" "${scope}" "opencode-command" "${parents_joined}"
          continue
        fi
        warn "  replacing command symlink ${target} (was → ${state#symlink:})"
        rm -f "${target}"
        ;;
      directory|file)
        if is_our_opencode_command_install "${source}" "${target}"; then
          ok "  command already installed: ${target}"
          manifest_upsert "${target}" "${method}" "${scope}" "opencode-command" "${parents_joined}"
          continue
        fi
        warn "  ${target} exists as ${state}; moving to ${target}.bak.$(date +%s)"
        mv "${target}" "${target}.bak.$(date +%s)"
        ;;
    esac

    if [[ "${method}" == "symlink" ]]; then
      ln -s "${source}" "${target}"
      ok "  command symlink: ${target} → ${source}"
    else
      cp "${source}" "${target}"
      ok "  command copied:  ${target}"
    fi
    manifest_upsert "${target}" "${method}" "${scope}" "opencode-command" "${parents_joined}"
  done < <(opencode_command_targets "${scope}")
}

remove_opencode_commands() {
  local scope="$1"
  local dry_run="$2"
  local source target parent
  local -a parents_to_prune=()
  OPENCODE_COMMAND_REMOVED=0

  while IFS=$'\t' read -r source target; do
    [[ -n "${source}" && -n "${target}" ]] || continue
    if [[ -e "${target}" || -L "${target}" ]] && is_our_opencode_command_install "${source}" "${target}"; then
      while IFS= read -r parent; do
        [[ -n "${parent}" ]] && parents_to_prune+=("${parent}")
      done < <(manifest_parents_for "${target}")
      if [[ "${dry_run}" == "1" ]]; then
        ok "  would remove command: ${target}"
        OPENCODE_COMMAND_REMOVED=$((OPENCODE_COMMAND_REMOVED + 1))
      elif [[ -L "${target}" ]]; then
        rm -f "${target}"
        ok "  removed command symlink: ${target}"
        manifest_remove_target "${target}"
        OPENCODE_COMMAND_REMOVED=$((OPENCODE_COMMAND_REMOVED + 1))
      else
        rm -f "${target}"
        ok "  removed command: ${target}"
        manifest_remove_target "${target}"
        OPENCODE_COMMAND_REMOVED=$((OPENCODE_COMMAND_REMOVED + 1))
      fi
    fi
  done < <(opencode_command_targets "${scope}")

  if ((${#parents_to_prune[@]} > 0)); then
    local -a unique_parents=()
    while IFS= read -r parent; do
      [[ -n "${parent}" ]] && unique_parents+=("${parent}")
    done < <(printf '%s\n' "${parents_to_prune[@]}" | awk '!seen[$0]++')
    prune_created_parents "${dry_run}" "${unique_parents[@]}"
  fi
}

run_uninstall_for_skill() {
  local slug="$1"
  local dry_run="${2:-0}"
  local -a targets=()
  local -a parents_to_prune=()
  local target removed=0 parent

  {
    activate_skill "${slug}"
    validate_skill_dir

    while IFS= read -r line; do
      [[ -n "${line}" ]] && targets+=("${line}")
    done < <(collect_install_targets)

    info "Removing ${SKILL_NAME} (source ${SKILL_DIR})"

    for target in "${targets[@]}"; do
      if [[ -e "${target}" || -L "${target}" ]] && is_our_skill_install "${target}"; then
        while IFS= read -r parent; do
          [[ -n "${parent}" ]] && parents_to_prune+=("${parent}")
        done < <(manifest_parents_for "${target}")
      fi
    done

    remove_opencode_commands "project" "${dry_run}"
    removed=$((removed + OPENCODE_COMMAND_REMOVED))
    remove_opencode_commands "user" "${dry_run}"
    removed=$((removed + OPENCODE_COMMAND_REMOVED))

    for target in "${targets[@]}"; do
      if [[ -e "${target}" || -L "${target}" ]]; then
        if is_our_skill_install "${target}"; then
          remove_one "${target}" "${dry_run}"
          removed=$((removed + 1))
        fi
      else
        remove_backups_near "${target}" "${dry_run}"
      fi
    done

    if ((${#parents_to_prune[@]} > 0)); then
      echo
      info "Pruning directories created for ${SKILL_NAME} (skipped if not empty)"
      local -a unique_parents=()
      while IFS= read -r line; do
        [[ -n "${line}" ]] && unique_parents+=("${line}")
      done < <(printf '%s\n' "${parents_to_prune[@]}" | awk '!seen[$0]++')
      prune_created_parents "${dry_run}" "${unique_parents[@]}"
    elif [[ "${removed}" -gt 0 ]] && [[ ! -f "${MANIFEST_FILE}" ]]; then
      echo
      warn "No install manifest for ${SKILL_NAME} — removed skill only; parent dirs preserved."
    fi
  } >&2

  echo "${removed}"
}

run_install_for_skill() {
  local slug="$1"
  local scope="$2"
  local method="$3"
  shift 3
  local -a ides=("$@")
  local ide target

  activate_skill "${slug}"
  validate_skill_dir

  info "Installing ${SKILL_NAME} (${method}, scope=${scope})"
  echo

  for ide in "${ides[@]}"; do
    target="$(ide_targets "${ide}" "${scope}")"
    info "$(ide_label "${ide}")"
    printf "  docs: %s\n" "$(ide_docs_url "${ide}")"
    install_one "${target}" "${method}" "${scope}" "${ide}"

    if [[ "${ide}" == "opencode" ]]; then
      info "OpenCode commands"
      install_opencode_commands "${scope}" "${method}"
    fi

    if [[ "${ide}" == "codex" && "${scope}" == "user" && -d "${HOME}/.codex" ]]; then
      local codex_home="${CODEX_HOME:-${HOME}/.codex}/skills/${SKILL_NAME}"
      install_one "${codex_home}" "${method}" "${scope}" "codex-home"
    fi
    echo
  done
}

run_install_batch() {
  local scope="$1"
  local method="$2"
  shift 2
  local -a skills=()
  local -a ides=()
  local slug

  while [[ $# -gt 0 && "$1" != "--" ]]; do
    skills+=("$1")
    shift
  done
  [[ "${1:-}" == "--" ]] && shift
  ides=("$@")

  for slug in "${skills[@]}"; do
    run_install_for_skill "${slug}" "${scope}" "${method}" "${ides[@]}"
  done

  cat <<EOF
${GREEN}Done.${RESET}

Installed skill(s): ${skills[*]}

Next steps:
  1. Reload your IDE (Developer: Reload Window) or restart the agent CLI.
  2. Open Customize → Skills and confirm the skill names appear.
  3. In OpenCode, invoke /${COMMAND_PREFIX}.docs or /${COMMAND_PREFIX}.admin.
EOF
}

detect_ides() {
  local -a found=()

  if [[ -n "${CURSOR_TRACE_ID:-}" || -n "${CURSOR_AGENT:-}" ]] || command -v cursor >/dev/null 2>&1; then
    found+=("cursor")
  fi

  if [[ "${TERM_PROGRAM:-}" == "vscode" || -n "${VSCODE_PID:-}" || -n "${VSCODE_CWD:-}" ]] \
     || command -v code >/dev/null 2>&1; then
    found+=("copilot")
  fi

  if command -v opencode >/dev/null 2>&1 || [[ -d "${HOME}/.config/opencode" ]]; then
    found+=("opencode")
  fi

  if command -v claude >/dev/null 2>&1 || [[ -d "${HOME}/.claude" ]]; then
    found+=("claude")
  fi

  if command -v codex >/dev/null 2>&1 || [[ -d "${HOME}/.codex" || -d "${HOME}/.agents/skills" ]]; then
    found+=("codex")
  fi

  if ((${#found[@]} == 0)); then
    found+=("agents")
  fi

  printf '%s\n' "${found[@]}" | awk '!seen[$0]++'
}

list_available_skills() {
  local slug mark
  ui "${BOLD}Available skills in ${SKILLS_ROOT}${RESET}"
  ui "${DIM}(auto-discovered from Skills/*/SKILL.md)${RESET}"
  ui ""
  for slug in $(discover_skills); do
    mark=""
    if ! skill_is_installed_anywhere "${slug}"; then
      mark=" ${YELLOW}[new / not installed]${RESET}"
    fi
    ui "  • ${slug}${mark} — $(skill_blurb "${slug}")"
  done
  ui ""
}

list_paths() {
  local slug
  cat <<EOF
${BOLD}Supported install targets (per skill)${RESET}

| IDE | Project scope | User scope |
|-----|---------------|------------|
| Cursor | .cursor/skills/<name> | ~/.cursor/skills/<name> |
| VS Code / GitHub Copilot | .github/skills/<name> | ~/.copilot/skills/<name> |
| OpenCode | .opencode/skills/<name> + .opencode/commands/discord.*.md | ~/.config/opencode/skills/<name> + ~/.config/opencode/commands/discord.*.md |
| Claude Code | .claude/skills/<name> | ~/.claude/skills/<name> |
| OpenAI Codex | .agents/skills/<name> | ~/.agents/skills/<name> |

Repo root: ${REPO_ROOT}
Skills folder: ${SKILLS_ROOT}

Skills discovered:
EOF
  for slug in $(discover_skills); do
    echo "  - ${slug}  →  Skills/${slug}/"
  done
}

show_banner() {
  ui ""
  ui "${BOLD}${CYAN}discord-bot Agent Skills Installer${RESET}"
  ui "${DIM}Register skills from Skills/ so your AI agent can discover and invoke them.${RESET}"
  ui ""
  ui "  Skills folder : ${SKILLS_ROOT}"
  ui "  Repo root     : ${REPO_ROOT}"
  ui ""
  list_available_skills
}

show_install_status() {
  local slug scope ide target status
  scope="project"
  ui "${BOLD}Install status (project scope)${RESET}"
  ui ""

  for slug in $(discover_skills); do
    activate_skill "${slug}"
    ui "  ${BOLD}${SKILL_NAME}${RESET}"
    for ide in cursor copilot opencode claude codex agents; do
      target="$(ide_targets "${ide}" "${scope}")"
      status="$(install_status_label "${target}")"
      ui "    $(ide_label "${ide}") → $(display_path "${target}")  [${status}]"
    done
    ui ""
  done
}

prompt_confirm() {
  local message="${1:-Proceed?}"
  local answer=""
  ask "${message} [y/N]: " answer
  [[ "${answer}" =~ ^[Yy]$ ]]
}

# Returns selected skill slugs one per line on stdout.
prompt_skills() {
  local prompt_title="${1:-Select skill(s)}"
  local default_all="${2:-1}"
  local -a menu_skills=()
  local -a selected=()
  local choice idx slug

  while IFS= read -r slug; do
    [[ -n "${slug}" ]] && menu_skills+=("${slug}")
  done < <(discover_skills)

  ui ""
  ui "${BOLD}${prompt_title}${RESET}"
  ui "${DIM}Enter numbers separated by spaces, 'a' for all, or press Enter for default.${RESET}"
  ui ""

  for idx in "${!menu_skills[@]}"; do
    slug="${menu_skills[$idx]}"
    ui "  ${GREEN}$((idx + 1)))${RESET} ${slug}"
    ui "      $(skill_blurb "${slug}")"
  done
  ui ""

  if [[ "${default_all}" == "1" ]]; then
    ask "Selection [all]: " choice
    if [[ -z "${choice}" ]]; then
      printf '%s\n' "${menu_skills[@]}"
      return 0
    fi
  else
    ask "Selection: " choice
    if [[ -z "${choice}" ]]; then
      warn "No skills selected."
      return 0
    fi
  fi

  if [[ "${choice}" =~ ^[Aa](ll)?$ ]]; then
    printf '%s\n' "${menu_skills[@]}"
    return 0
  fi

  for idx in ${choice}; do
    if [[ "${idx}" =~ ^[0-9]+$ ]] && (( idx >= 1 && idx <= ${#menu_skills[@]} )); then
      selected+=("${menu_skills[$((idx - 1))]}")
    else
      warn "Ignoring invalid selection: ${idx}"
    fi
  done

  if ((${#selected[@]} == 0)); then
    warn "No valid skills selected; using all skills."
    printf '%s\n' "${menu_skills[@]}"
    return 0
  fi

  printf '%s\n' "${selected[@]}" | awk '!seen[$0]++'
}

prompt_scope() {
  local choice
  ui ""
  ui "${BOLD}Step 2/4 — Install scope${RESET}"
  ui ""
  ui "  ${GREEN}1)${RESET} Project ${DIM}(recommended)${RESET}"
  ui "     Installs into this repo (e.g. .cursor/skills/<skill-name>)."
  ui ""
  ui "  2) User (global)"
  ui "     Installs into your home directory — available in every repo."
  ui ""
  ask "Scope [1]: " choice

  case "${choice:-1}" in
    1|project|p) echo "project" ;;
    2|user|u)    echo "user" ;;
    *)
      warn "Invalid choice; defaulting to project scope."
      echo "project"
      ;;
  esac
}

prompt_method() {
  local choice
  ui ""
  ui "${BOLD}Step 4/4 — Install method${RESET}"
  ui ""
  ui "  ${GREEN}1)${RESET} Symlink ${DIM}(recommended)${RESET}"
  ui "     One source tree under Skills/<name>/ — IDE folders point here."
  ui ""
  ui "  2) Copy"
  ui "     Full duplicate per IDE path. Use only if symlinks are not allowed."
  ui ""
  ask "Method [1]: " choice

  case "${choice:-1}" in
    1|symlink|s|ln) echo "symlink" ;;
    2|copy|c)       echo "copy" ;;
    *)
      warn "Invalid choice; defaulting to symlink."
      echo "symlink"
      ;;
  esac
}

prompt_ides() {
  local scope="${1:-project}"
  local skill_slug="${2:-}"
  local -a detected=()
  local -a menu_keys=("cursor" "copilot" "opencode" "claude" "codex" "agents")
  local -a selected=()
  local choice target status idx key label det_mark

  if [[ -n "${skill_slug}" ]]; then
    activate_skill "${skill_slug}"
  fi

  while IFS= read -r line; do
    [[ -n "${line}" ]] && detected+=("${line}")
  done < <(detect_ides)

  ui ""
  ui "${BOLD}Step 3/4 — Select IDE(s)${RESET}"
  if [[ -n "${skill_slug}" ]]; then
    ui "${DIM}Paths shown for skill: ${skill_slug} (scope: ${scope})${RESET}"
  fi
  ui ""

  for idx in "${!menu_keys[@]}"; do
    key="${menu_keys[$idx]}"
    label="$(ide_label "${key}")"
    target="$(ide_targets "${key}" "${scope}")"
    status="$(install_status_label "${target}")"
    det_mark=""
    if printf '%s\n' "${detected[@]}" | grep -qx "${key}"; then
      det_mark=" ${GREEN}[detected]${RESET}"
    fi
    ui "  ${GREEN}$((idx + 1)))${RESET} ${label}${det_mark}"
    ui "      → $(display_path "${target}")  [${status}]"
  done

  ui ""
  ui "${DIM}Enter one or more numbers separated by spaces.${RESET}"
  ui "${DIM}Press Enter for detected IDE(s) only, or 'a' for all.${RESET}"
  ask "Selection [detected]: " choice

  if [[ -z "${choice}" ]]; then
    if ((${#detected[@]} > 0)); then
      printf '%s\n' "${detected[@]}"
      return 0
    fi
    echo "agents"
    return 0
  fi

  if [[ "${choice}" =~ ^[Aa](ll)?$ ]]; then
    printf '%s\n' "${menu_keys[@]}"
    return 0
  fi

  for idx in ${choice}; do
    if [[ "${idx}" =~ ^[1-6]$ ]]; then
      key="${menu_keys[$((idx - 1))]}"
      selected+=("${key}")
    else
      warn "Ignoring invalid selection: ${idx}"
    fi
  done

  if ((${#selected[@]} == 0)); then
    warn "No valid IDE selected; defaulting to detected environments."
    if ((${#detected[@]} > 0)); then
      printf '%s\n' "${detected[@]}"
    else
      echo "agents"
    fi
    return 0
  fi

  printf '%s\n' "${selected[@]}" | awk '!seen[$0]++'
}

show_install_summary() {
  local scope="$1"
  local method="$2"
  shift 2
  local -a skills=()
  local -a ides=()
  local slug ide target

  while [[ $# -gt 0 && "$1" != "--" ]]; do
    skills+=("$1")
    shift
  done
  [[ "${1:-}" == "--" ]] && shift
  ides=("$@")

  ui ""
  ui "${BOLD}Install summary${RESET}"
  ui "  Skills : ${skills[*]}"
  ui "  Scope  : ${scope}"
  ui "  Method : ${method}"
  ui "  IDEs   : $(printf '%s ' "${ides[@]}")"
  ui ""
  ui "  Targets (first skill path pattern; repeated per skill):"

  if ((${#skills[@]} > 0)); then
    activate_skill "${skills[0]}"
    for ide in "${ides[@]}"; do
      target="$(ide_targets "${ide}" "${scope}")"
      ui "    • $(ide_label "${ide}") → $(display_path "${target}")"
    done
    if ((${#skills[@]} > 1)); then
      ui "    ${DIM}…same IDE folders for: ${skills[*]:1}${RESET}"
    fi
  fi
  ui ""
}

run_quick_install() {
  local -a skills=()
  local -a ides=()
  local scope="project"
  local method="symlink"
  local ide

  while IFS= read -r line; do
    [[ -n "${line}" ]] && skills+=("${line}")
  done < <(prompt_skills "Step 1/1 — Skills to install" "1")

  if ((${#skills[@]} == 0)); then
    warn "No skills selected; cancelled."
    return 0
  fi

  while IFS= read -r line; do
    [[ -n "${line}" ]] && ides+=("${line}")
  done < <(detect_ides)

  if ((${#ides[@]} == 0)); then
    ides=("agents")
    ui "${YELLOW}No IDE detected — using universal .agents/skills/.${RESET}"
  else
    ui "${BOLD}Detected IDE(s):${RESET}"
    for ide in "${ides[@]}"; do
      ui "  • $(ide_label "${ide}")"
    done
  fi

  show_install_summary "${scope}" "${method}" "${skills[@]}" -- "${ides[@]}"

  if ! prompt_confirm "Install now?"; then
    warn "Install cancelled."
    return 0
  fi

  run_install_batch "${scope}" "${method}" "${skills[@]}" -- "${ides[@]}"
}

run_custom_install_wizard() {
  local -a skills=()
  local -a ides=()
  local scope method first_skill

  while IFS= read -r line; do
    [[ -n "${line}" ]] && skills+=("${line}")
  done < <(prompt_skills "Step 1/4 — Skills to install" "0")

  if ((${#skills[@]} == 0)); then
    warn "No skills selected; cancelled."
    return 0
  fi

  scope="$(prompt_scope)"
  first_skill="${skills[0]}"
  while IFS= read -r line; do
    [[ -n "${line}" ]] && ides+=("${line}")
  done < <(prompt_ides "${scope}" "${first_skill}")
  method="$(prompt_method)"

  show_install_summary "${scope}" "${method}" "${skills[@]}" -- "${ides[@]}"

  if ! prompt_confirm "Install now?"; then
    warn "Install cancelled."
    return 0
  fi

  run_install_batch "${scope}" "${method}" "${skills[@]}" -- "${ides[@]}"
}

run_interactive_uninstall() {
  local -a skills=()
  local slug total=0 removed dry_run=0

  while IFS= read -r line; do
    [[ -n "${line}" ]] && skills+=("${line}")
  done < <(prompt_skills "Skills to uninstall" "0")

  if ((${#skills[@]} == 0)); then
    warn "No skills selected; cancelled."
    return 0
  fi

  ui ""
  if ! prompt_confirm "Uninstall selected skill(s): ${skills[*]} ?"; then
    warn "Uninstall cancelled."
    return 0
  fi

  for slug in "${skills[@]}"; do
    removed="$(run_uninstall_for_skill "${slug}" "${dry_run}")"
    total=$((total + removed))
    echo
  done

  if [[ "${total}" -eq 0 ]]; then
    ok "Uninstall complete. No active installs found for selected skills."
  else
    ok "Uninstall complete. Removed ${total} install target(s) across selected skills."
  fi
}

run_interactive() {
  validate_skills_root
  show_banner

  while true; do
    local action choice
    local -a missing_preview=()
    while IFS= read -r line; do
      [[ -n "${line}" ]] && missing_preview+=("${line}")
    done < <(list_missing_skills)

    ui "${BOLD}What would you like to do?${RESET}"
    ui ""
    ui "  ${GREEN}1)${RESET} Sync new skills ${DIM}(auto-detect missing; reuse prior IDE prefs)${RESET}"
    if ((${#missing_preview[@]} > 0)); then
      ui "     ${YELLOW}pending: ${missing_preview[*]}${RESET}"
    else
      ui "     ${DIM}nothing pending${RESET}"
    fi
    ui "  2) Quick install ${DIM}(pick skills + detected IDE)${RESET}"
    ui "  3) Custom install ${DIM}(skills, scope, IDE, method)${RESET}"
    ui "  4) Uninstall ${DIM}(pick skills)${RESET}"
    ui "  5) Show status"
    ui "  6) List IDE paths"
    ui "  7) Exit"
    ui ""
    ask "Choice [1]: " choice

    case "${choice:-1}" in
      1|sync)
        run_sync
        return 0
        ;;
      2|quick|install)
        run_quick_install
        return 0
        ;;
      3|custom)
        run_custom_install_wizard
        return 0
        ;;
      4|uninstall|remove)
        run_interactive_uninstall
        return 0
        ;;
      5|status)
        show_install_status
        ;;
      6|list|paths)
        ui ""
        list_paths
        ui ""
        ;;
      7|exit|quit)
        ui "Bye."
        return 0
        ;;
      *)
        warn "Invalid choice; try again."
        ;;
    esac
  done
}

parse_skill_slugs_from_args() {
  local -a slugs=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --skill)
        [[ -n "${2:-}" ]] || die "--skill requires a name"
        slugs+=("$2")
        shift 2
        ;;
      --all)
        while IFS= read -r slug; do
          [[ -n "${slug}" ]] && slugs+=("${slug}")
        done < <(discover_skills)
        shift
        ;;
      *)
        shift
        ;;
    esac
  done
  if ((${#slugs[@]} > 0)); then
    printf '%s\n' "${slugs[@]}" | awk '!seen[$0]++'
  fi
}

run_auto() {
  local -a skills=()
  local -a ides=()
  local -a cli_skills=()

  while IFS= read -r line; do
    [[ -n "${line}" ]] && cli_skills+=("${line}")
  done < <(parse_skill_slugs_from_args "$@")

  if ((${#cli_skills[@]} > 0)); then
    skills=("${cli_skills[@]}")
  else
    while IFS= read -r line; do
      [[ -n "${line}" ]] && skills+=("${line}")
    done < <(discover_skills)
  fi

  while IFS= read -r line; do
    [[ -n "${line}" ]] && ides+=("${line}")
  done < <(detect_ides)
  if ((${#ides[@]} == 0)); then
    ides=("agents")
  fi

  for slug in "${skills[@]}"; do
    [[ -d "${SKILLS_ROOT}/${slug}" ]] || die "Unknown skill: ${slug}"
  done

  run_install_batch "project" "symlink" "${skills[@]}" -- "${ides[@]}"
}

# Install skills that exist under Skills/ but are missing from prior IDE targets.
# Reuses scope/method/IDE from existing .install-manifest files when present.
run_sync() {
  local -a missing=()
  local -a prefs=()
  local slug line scope method ide target
  local has_prefs=0

  validate_skills_root

  while IFS= read -r line; do
    [[ -n "${line}" ]] && missing+=("${line}")
  done < <(list_missing_skills)

  while IFS= read -r line; do
    [[ -n "${line}" ]] && prefs+=("${line}") && has_prefs=1
  done < <(infer_install_prefs || true)

  if ((${#missing[@]} == 0)); then
    ok "All discovered skills already installed at known targets."
    list_available_skills
    return 0
  fi

  info "Discovered ${#missing[@]} new/missing skill(s): ${missing[*]}"

  if [[ "${has_prefs}" -eq 0 ]]; then
    local -a ides=()
    info "No prior install manifests — installing missing skills (detected IDE, project, symlink)."
    while IFS= read -r line; do
      [[ -n "${line}" ]] && ides+=("${line}")
    done < <(detect_ides)
    if ((${#ides[@]} == 0)); then
      ides=("agents")
    fi
    run_install_batch "project" "symlink" "${missing[@]}" -- "${ides[@]}"
    return 0
  fi

  info "Reusing install prefs from existing manifests:"
  for line in "${prefs[@]}"; do
    IFS=$'\t' read -r scope method ide <<< "${line}"
    ui "  • $(ide_label "${ide}")  scope=${scope}  method=${method}"
  done
  echo

  for slug in "${missing[@]}"; do
    activate_skill "${slug}"
    validate_skill_dir
    info "Syncing ${SKILL_NAME}"
    echo
    for line in "${prefs[@]}"; do
      IFS=$'\t' read -r scope method ide <<< "${line}"
      target="$(ide_targets "${ide}" "${scope}")" || continue
      info "$(ide_label "${ide}")"
      printf "  docs: %s\n" "$(ide_docs_url "${ide}")"
      install_one "${target}" "${method}" "${scope}" "${ide}"
      if [[ "${ide}" == "codex" && "${scope}" == "user" && -d "${HOME}/.codex" ]]; then
        local codex_home="${CODEX_HOME:-${HOME}/.codex}/skills/${SKILL_NAME}"
        install_one "${codex_home}" "${method}" "${scope}" "codex-home"
      fi
      echo
    done
  done

  cat <<EOF
${GREEN}Sync done.${RESET}

Installed new/missing skill(s): ${missing[*]}

Next steps:
  1. Reload your IDE (Developer: Reload Window) or restart the agent CLI.
  2. Confirm the new skill names appear under Customize → Skills.
  3. In OpenCode, invoke /${COMMAND_PREFIX}.docs or /${COMMAND_PREFIX}.admin.
EOF
}

run_cli_uninstall() {
  local dry_run=0
  local -a skills=()
  local -a args=()
  local slug removed total=0

  for arg in "$@"; do
    case "${arg}" in
      --dry-run) dry_run=1 ;;
      *) args+=("${arg}") ;;
    esac
  done

  while IFS= read -r line; do
    [[ -n "${line}" ]] && skills+=("${line}")
  done < <(parse_skill_slugs_from_args "${args[@]}")

  if ((${#skills[@]} == 0)); then
    while IFS= read -r line; do
      [[ -n "${line}" ]] && skills+=("${line}")
    done < <(discover_skills)
  fi

  validate_skills_root

  if [[ "${dry_run}" == "1" ]]; then
    warn "Dry run — no files will be deleted."
  fi

  for slug in "${skills[@]}"; do
    removed="$(run_uninstall_for_skill "${slug}" "${dry_run}")"
    total=$((total + removed))
    echo
  done

  if [[ "${dry_run}" == "1" ]]; then
    ok "Dry run complete."
  elif [[ "${total}" -eq 0 ]]; then
    ok "Uninstall complete. No active installs found."
  else
    ok "Uninstall complete. Removed ${total} install target(s)."
  fi
}

main() {
  validate_skills_root

  case "${1:-}" in
    --help|-h)
      usage
      ;;
    --skills)
      list_available_skills
      ;;
    --list|-l)
      list_paths
      ;;
    --uninstall|-u)
      shift
      run_cli_uninstall "$@"
      ;;
    --auto|-a)
      shift
      run_auto "$@"
      ;;
    --sync|-s)
      run_sync
      ;;
    "")
      run_interactive
      ;;
    *)
      err "Unknown option: $1"
      usage >&2
      exit 1
      ;;
  esac
}

main "$@"
