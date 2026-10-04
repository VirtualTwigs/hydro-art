#!/usr/bin/env bash
# Generate deploy/riverglyph.env with a long random passphrase used as both user and password
# (user = password; 8 dictionary words + 2 digits, from a CSPRNG). Won't overwrite an existing file.
set -euo pipefail
cd "$(dirname "$0")"
out=riverglyph.env
if [[ -e "$out" ]]; then
  echo "$out already exists; delete it first to rotate the password." >&2
  exit 1
fi
phrase=$(python3 - <<'PY'
import re, secrets
words = sorted({w.strip().lower() for w in open("/usr/share/dict/words")
                if re.fullmatch(r"[A-Za-z]{4,8}", w.strip())})
picks = [secrets.choice(words) for _ in range(8)]
print("-".join(picks) + f"-{secrets.randbelow(90) + 10}")
PY
)
umask 077
printf 'RIVERGLYPH_USER=%s\nRIVERGLYPH_PASSWORD=%s\n' "$phrase" "$phrase" > "$out"
echo "Wrote deploy/$out"
echo "  user:     $phrase  (same as password)"
echo "  password: $phrase"
