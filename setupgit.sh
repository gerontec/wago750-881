#!/bin/bash
# Git Repository Setup für WAGO Heizungssteuerung
# SSH-Key bereits in GitHub vorhanden: kellertreppe

set -e

echo "========================================="
echo "Git Repository Setup"
echo "========================================="

REPO_NAME="wago-heizung"
GITHUB_USER="gerontec"

# Git Config
echo "Git Konfiguration..."
git config --global user.name "$GITHUB_USER"
git config --global user.email "${GITHUB_USER}@users.noreply.github.com"
git config --global init.defaultBranch main
echo "✓ Git konfiguriert"

# Erstelle lokales Repository
echo ""
echo "Wechsle zu ~/python..."
cd ~/python

# Git Init
if [ ! -d .git ]; then
    git init
    echo "✓ Git Repository initialisiert"
else
    echo "✓ Git Repository existiert bereits"
fi

# Kopiere Dateien
echo ""
echo "Kopiere README und .gitignore..."
cp /mnt/user-data/outputs/README.md . 2>/dev/null || echo "README.md bereits vorhanden"
cp /mnt/user-data/outputs/.gitignore . 2>/dev/null || echo ".gitignore bereits vorhanden"

# Stage Dateien
echo ""
echo "Stage Dateien..."
git add README.md .gitignore
git add heizung_v6.4.8.st heizung_v6.4.8_globals.txt 2>/dev/null || true
git add heizung2.py heizung3.py reset_runtime.py 2>/dev/null || true

echo ""
echo "Status:"
git status --short

# Commit
echo ""
read -p "Commit erstellen? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    git commit -m "Initial commit - WAGO 750-881 Heizungssteuerung v6.4.8

- SPS v6.4.8: Vereinfachte WW-Regel (ΔT ≥ 2°C)
- Python v3.8.3 (heizung3.py - Monitoring)
- Python v3.9.1 (heizung2.py - Datenlogger)
- MySQL Schema V7 mit Runtime
- OSCAT ACTUATOR_PUMP Integration
- Grafische DI/DO-Anzeige
"
    echo "✓ Commit erstellt"
fi

echo ""
echo "========================================="
echo "Nächster Schritt:"
echo "========================================="
echo ""
echo "1. Erstelle GitHub Repository:"
echo "   https://github.com/new"
echo ""
echo "   Name: $REPO_NAME"
echo "   Beschreibung: WAGO 750-881 Heizungssteuerung"
echo "   Public/Private: Nach Wunsch"
echo "   ⚠️ OHNE README/.gitignore/License"
echo ""
echo "2. Dann ausführen:"
echo "   git remote add origin git@github.com:${GITHUB_USER}/${REPO_NAME}.git"
echo "   git push -u origin main"
echo ""
