#!/usr/bin/env bash
# Copy dashboard + hydrated data into docs/ for GitHub Pages
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$ROOT/docs/dashboard" "$ROOT/docs/data"
mkdir -p "$ROOT/docs"
cp -R "$ROOT/dashboard" "$ROOT/docs/dashboard"
mkdir -p "$ROOT/docs/data"
for f in workorders.json assets.json locations.json locations_tree.json meta.json compliance_rules.json; do
  [ -f "$ROOT/data/$f" ] && cp "$ROOT/data/$f" "$ROOT/docs/data/"
done
[ -f "$ROOT/data/public/nyc_open_data.json" ] && mkdir -p "$ROOT/docs/data/public" && cp "$ROOT/data/public/nyc_open_data.json" "$ROOT/docs/data/public/"
[ -f "$ROOT/data/closure_log.json" ] && cp "$ROOT/data/closure_log.json" "$ROOT/docs/data/"
cat > "$ROOT/docs/index.html" <<'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
  <meta http-equiv="refresh" content="0; url=cover.html" />
  <title>Team 12 — 240 2nd Avenue</title>
</head>
<body>
  <p><a href="cover.html">Cover</a> · <a href="http://3.94.205.179:8787/cover.html">Live AWS</a> · <a href="deck.html">Deck</a> · <a href="dashboard/index.html">Dashboard</a></p>
</body>
</html>
EOF
touch "$ROOT/docs/.nojekyll"
echo "Synced to docs/"
echo "  Submission: docs/submission.html"
echo "  Dashboard:  docs/dashboard/index.html"
