#!/usr/bin/env bash
# Responsive-adapter static scanner
# Usage: scan.sh <project-root>
# Outputs: structured issue list (severity, file:line, anti-pattern, snippet)

set -u
ROOT="${1:-.}"

if [[ ! -d "$ROOT" ]]; then
  echo "ERROR: not a directory: $ROOT" >&2
  exit 1
fi

# Shared scope rules — keep grep --exclude-dir and find -prune in sync.
# Note: public/ is NOT excluded — it commonly holds source index.html in Vite/Next/Astro/Vue.
# Build outputs (dist, build, out, .next, .nuxt, .svelte-kit) are excluded explicitly.
EXCLUDE_DIRS=(node_modules .next .nuxt dist build out coverage .git .cache .svelte-kit .turbo .vercel .parcel-cache)

# colors disabled for grep-friendly output
GREP_OPTS="-rn \
--include=*.html --include=*.htm \
--include=*.css --include=*.scss --include=*.sass --include=*.less \
--include=*.tsx --include=*.jsx --include=*.ts --include=*.js \
--include=*.vue --include=*.svelte --include=*.astro \
--exclude=*.min.css --exclude=*.min.js"
for d in "${EXCLUDE_DIRS[@]}"; do
  GREP_OPTS="$GREP_OPTS --exclude-dir=$d"
done

# find_files <ext1> [ext2 ...] — find source files matching extensions,
# pruning the standard excluded directories (same as grep --exclude-dir).
# Uses argv directly — no eval — so parens are passed to find as literal tokens.
find_files() {
  local prune=("(")
  local pfirst=1
  for d in "${EXCLUDE_DIRS[@]}"; do
    if [[ "$pfirst" -eq 1 ]]; then
      prune+=(-name "$d"); pfirst=0
    else
      prune+=(-o -name "$d")
    fi
  done
  prune+=(")" -prune -o)

  local match=("(")
  local mfirst=1
  for ext in "$@"; do
    if [[ "$mfirst" -eq 1 ]]; then
      match+=(-name "*.$ext"); mfirst=0
    else
      match+=(-o -name "*.$ext")
    fi
  done
  match+=(")" -type f -print)

  find "$ROOT" "${prune[@]}" "${match[@]}" 2>/dev/null
}

# Export so `bash -c '...'` subshells inside section() can use find_files.
# Arrays can't be exported, so re-declare EXCLUDE_DIRS inside an exportable wrapper.
__EXCLUDE_DIRS_JOINED="$(printf '%s\n' "${EXCLUDE_DIRS[@]}")"
export ROOT __EXCLUDE_DIRS_JOINED
find_files_subshell() {
  local IFS=$'\n'
  # shellcheck disable=SC2206
  EXCLUDE_DIRS=( $__EXCLUDE_DIRS_JOINED )
  find_files "$@"
}
export -f find_files find_files_subshell

echo "# Responsive Static Scan — $ROOT"
echo "# generated $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo

# Helper: print group header only if matches exist
section() {
  local title="$1"; shift
  local out
  out="$("$@" 2>/dev/null || true)"
  if [[ -n "$out" ]]; then
    echo "## $title"
    echo
    echo "$out"
    echo
  fi
}

# ------- CRITICAL -------

# A1 — missing viewport meta
section "[CRITICAL] A1: HTML files missing viewport meta" \
  bash -c '
    while IFS= read -r f; do
      if ! grep -qiE "<meta[^>]+name=[\"'"'"']viewport[\"'"'"']" "$f"; then
        echo "$f:1 — no <meta name=\"viewport\"> found"
      fi
    done < <(find_files_subshell html htm)
  '

# A2 — disabled pinch-zoom
section "[CRITICAL] A2: pinch-zoom disabled (WCAG 1.4.4 violation)" \
  grep $GREP_OPTS -iE "(maximum-scale=1|user-scalable=no|minimum-scale=1)" "$ROOT"

# A4 — input font-size < 16px
section "[CRITICAL] A4: input/textarea with font-size < 16px (iOS zoom bug)" \
  grep $GREP_OPTS -iE "(input|textarea|select)[^{]{0,200}font-size:\s*(0\.[0-9]+|[1-9](\.[0-9]+)?|1[0-5](\.[0-9]+)?)px" "$ROOT"

# A3 — fixed pixel width
section "[CRITICAL] A3: fixed width:\\s*\\d{3,}px (likely blocks shrinkage)" \
  grep $GREP_OPTS -iE "(^|[^-])width:\s*[0-9]{3,}px[^a-z]" "$ROOT"

# A3 — large min-width
section "[CRITICAL] A3b: large min-width (silent layout lockup)" \
  grep $GREP_OPTS -iE "min-width:\s*[3-9][0-9]{2,}px" "$ROOT"

# A3 — Tailwind arbitrary fixed width / min-width >= 100px
section "[CRITICAL] A3-tw: Tailwind arbitrary fixed width (w-[Npx] / min-w-[Npx])" \
  grep $GREP_OPTS -E "(^|[^a-zA-Z])(w|min-w)-\[[0-9]{3,}px\]" "$ROOT"

# A4-tw — Tailwind arbitrary text-[<16px] (broad regex — catches ALL uses,
# not just inputs; verify each hit. If applied to <input>/<textarea>/<select>,
# triggers iOS Safari auto-zoom on focus. On purely decorative text it's only
# a readability concern.)
section "[MAJOR] A4-tw: Tailwind arbitrary text-[<16px] (verify none applied to form controls — iOS zoom)" \
  grep $GREP_OPTS -E "text-\[(1[0-5]|[1-9])px\]" "$ROOT"

# ------- MAJOR -------

# A5-tw — Tailwind h-screen / min-h-screen without dvh equivalent
section "[MAJOR] A5-tw: Tailwind h-screen / min-h-screen (prefer h-dvh / min-h-dvh / h-svh)" \
  bash -c '
    grep '"$GREP_OPTS"' -E "(^|[^a-zA-Z])(min-)?h-screen([^a-zA-Z]|\$)" "'"$ROOT"'" 2>/dev/null | grep -v -E "h-(dvh|svh|lvh)"
  '

# A5 — 100vh without dvh/svh fallback nearby
# False-positive-aware: ignore lines where the same property has a 100svh/100dvh/100lvh
# override within 3 lines (progressive-enhancement pattern is correct usage).
section "[MAJOR] A5: 100vh without dvh/svh fallback" \
  bash -c '
    while IFS=: read -r f ln rest; do
      [[ -z "$f" ]] && continue
      # check ±3 lines for dvh/svh/lvh fallback
      start=$(( ln > 3 ? ln - 3 : 1 ))
      end=$(( ln + 3 ))
      if ! sed -n "${start},${end}p" "$f" 2>/dev/null | grep -qE "(dvh|svh|lvh)"; then
        echo "$f:$ln —$rest"
      fi
    done < <(grep '"$GREP_OPTS"' -iE "100vh" "'"$ROOT"'" 2>/dev/null | grep -v -iE "(dvh|svh|lvh)")
  '

# A8 — missing fluid image baseline (multi-line aware, accepts physical or logical props)
section "[MAJOR] A8: no fluid image rule (img { max-width: 100% } or max-inline-size: 100%)" \
  bash -c '
    has_rule=0
    while IFS= read -r f; do
      # use awk to handle multi-line rule blocks
      if awk "BEGIN{f=0;ok=0}
              /^[[:space:]]*(\*|img|html|body)([[:space:]]|,)/{f=1}
              f && /\{/{}
              f && /max-(width|inline-size)[[:space:]]*:[[:space:]]*100%/{ok=1}
              f && /\}/{f=0}
              END{exit ok?0:1}" "$f" 2>/dev/null; then
        has_rule=1; break
      fi
    done < <(find_files_subshell css scss)
    if [[ "$has_rule" -eq 0 ]]; then
      echo "(global) — no rule found ensuring images shrink with viewport"
    fi
  '

# A14 — overflow:hidden on body
section "[MAJOR] A14: overflow:hidden on body/html (masking root overflow)" \
  grep $GREP_OPTS -iE "(body|html)[^{]{0,50}\{[^}]*overflow(-x)?:\s*hidden" "$ROOT"

# A14-tw — Tailwind overflow-hidden on body/html-level elements
section "[MAJOR] A14-tw: Tailwind overflow-hidden on body / root layout (prefer overflow-x-clip)" \
  grep $GREP_OPTS -E "<(body|html)[^>]*class=[\"'][^\"']*overflow-(x-)?hidden" "$ROOT"

# A9 — fixed position bottom without safe-area-inset
section "[MAJOR] A9: position:fixed bottom without safe-area-inset" \
  bash -c '
    grep '"$GREP_OPTS"' -iE "position:\s*fixed[^}]{0,200}bottom" "'"$ROOT"'" 2>/dev/null | grep -v "safe-area-inset"
  '

# A13 — 100vw usage (potential scrollbar overflow)
section "[MAJOR] A13: 100vw usage (includes scrollbar — may overflow)" \
  grep $GREP_OPTS -iE "100vw" "$ROOT"

# Table without overflow wrapper (heuristic)
section "[MAJOR] Table elements (verify each is wrapped in overflow-x ancestor)" \
  bash -c '
    grep '"$GREP_OPTS"' -iE "<table[\s>]" "'"$ROOT"'" 2>/dev/null | head -20
  '

# A11 — hardcoded px in headings/paddings
section "[MAJOR] A11: font-size in px on headings (consider rem/clamp)" \
  grep $GREP_OPTS -iE "(^|[^a-z])(h[1-6]|\\.h[1-6])[^{]{0,50}\{[^}]*font-size:\s*[0-9]+px" "$ROOT"

# A15 — hover-only menus
section "[MAJOR] A15: :hover reveal without :focus-within fallback" \
  bash -c '
    grep '"$GREP_OPTS"' -iE ":hover\s*[^{]{0,40}\{[^}]*(display:\s*block|visibility:\s*visible|opacity:\s*1)" "'"$ROOT"'" 2>/dev/null | grep -v ":focus-within"
  '

# ------- MINOR -------

# A17 — X-UA-Compatible
section "[MINOR] A17: legacy X-UA-Compatible meta (remove)" \
  grep $GREP_OPTS -iE "http-equiv=[\"']?X-UA-Compatible" "$ROOT"

# A12 — text-align: justify
section "[MINOR] A12: text-align: justify (rivers on narrow widths)" \
  grep $GREP_OPTS -iE "text-align:\s*justify" "$ROOT"

# No text-size-adjust set anywhere in the stylesheet (multi-line aware)
section "[MINOR] text-size-adjust not set (iOS landscape inflates fonts)" \
  bash -c '
    has=0
    while IFS= read -r f; do
      if grep -qE "(-webkit-)?text-size-adjust" "$f"; then
        has=1; break
      fi
    done < <(find_files_subshell css scss)
    [[ "$has" -eq 0 ]] && echo "(global) — recommend html { -webkit-text-size-adjust: 100%; text-size-adjust: 100%; }"
  '

# Inline style attributes (often used to bypass responsive CSS)
section "[MINOR] inline style=\"width:Npx\" (bypasses stylesheet responsive rules)" \
  grep $GREP_OPTS -iE "style=\"[^\"]*width:\s*[0-9]{3,}px" "$ROOT"

echo "# End of scan"
echo "#"
echo "# Note: this is a static heuristic scan. Some findings are false positives"
echo "# (e.g., width:1200px on a desktop-only decoration is fine). Triage by severity."
echo "# Always verify in a real browser at the device matrix — see references/device-matrix.md"
