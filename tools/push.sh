#!/bin/bash
# Push "a mano, ma completo": riallinea la dashboard a Grafana, mette tutto nel
# commit e pusha. Si lancia solo quando decidiamo di pushare.
#
#   tools/push.sh "feat(gui): ..."
set -euo pipefail
cd "$(dirname "$0")/.."

msg="${1:-chore: update}"

# 1. la dashboard viva entra nel commit: se il file era indietro viene riscritto
if python3 tools/sync_dashboard.py; then :; else
  echo "⚠️  dashboard non riallineata (Grafana non raggiungibile?): procedo col file com'è"
fi

# 2. commit, solo se c'è qualcosa
git add -A
if git diff --cached --quiet; then
  echo "niente da committare"
else
  git commit -m "$msg"
fi

# 3. push, sempre
git push origin main
git log -1 --format='%h %s'
