#!/usr/bin/env bash
# Copy dashboard + hydrated data into docs/ for GitHub Pages
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
rm -rf "$ROOT/docs/dashboard" "$ROOT/docs/data"
mkdir -p "$ROOT/docs"
cp -R "$ROOT/dashboard" "$ROOT/docs/dashboard"
if [ -d "$ROOT/data" ]; then
  mkdir -p "$ROOT/docs/data"
  for f in workorders.json assets.json locations.json locations_tree.json; do
    [ -f "$ROOT/data/$f" ] && cp "$ROOT/data/$f" "$ROOT/docs/data/"
  done
fi
cat > "$ROOT/docs/index.html" <<'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
  <meta http-equiv="refresh" content="0; url=dashboard/index.html" />
  <title>240 2nd Avenue Dashboard</title>
</head>
<body><p><a href="dashboard/index.html">Work Orders Dashboard</a></p></body>
</html>
EOF
# GitHub Pages: data lives alongside dashboard
sed -i '' 's|data-data-base="../data"|data-data-base="../data"|' "$ROOT/docs/dashboard/index.html" 2>/dev/null || \
  sed -i 's|data-data-base="../data"|data-data-base="../data"|' "$ROOT/docs/dashboard/index.html"
echo "Synced to docs/ — commit and push for GitHub Pages"
