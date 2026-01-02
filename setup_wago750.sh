#!/bin/bash
# Git Repository Setup für ~/wago750-881
# Projekt: WAGO 750-881 Heizungssteuerung

set -e

REPO_NAME="wago750-881"
GITHUB_USER="gerontec"
PROJECT_DIR="$HOME/wago750-881"

echo "========================================="
echo "Git Repository Setup: $REPO_NAME"
echo "========================================="
echo ""

# Wechsle ins Projektverzeichnis
cd "$PROJECT_DIR"
echo "✓ Verzeichnis: $PROJECT_DIR"
echo ""

# Zeige vorhandene Dateien
echo "Vorhandene Dateien:"
ls -lh
echo ""

# Git Config
echo "Git Konfiguration..."
git config --global user.name "$GITHUB_USER"
git config --global user.email "${GITHUB_USER}@users.noreply.github.com"
git config --global init.defaultBranch main
echo "✓ Git konfiguriert"
echo ""

# Git Init
if [ ! -d .git ]; then
    git init
    echo "✓ Git Repository initialisiert"
else
    echo "✓ Git Repository existiert bereits"
fi
echo ""

# Erstelle/kopiere README.md
if [ ! -f README.md ]; then
    echo "Erstelle README.md..."
    cat > README.md << 'EOF'
# WAGO 750-881 Heizungssteuerung

Heizungssteuerung für WAGO 750-881 PLC mit Python-Monitoring und MySQL-Datenlogging.

## Übersicht

Steuerung einer Ölheizung mit 3 Pumpen (Warmwasser, Heizkreis, Brunnenpumpe).

### Hardware
- **PLC**: WAGO 750-881 (Modbus TCP)
- **Sensoren**: 5× PT1000, 2× NTC, 1× Öltank
- **Ausgänge**: 3× Pumpen + Multiplexer
- **Eingänge**: 8-Kanal DI-Karte

## Komponenten

### SPS v6.4.8
- **heizung_v6.4.8.st** - Hauptprogramm (Structured Text)
- **heizung_v6.4.8_globals.txt** - Globale Variablen
- **Features**: ΔT-Regel (≥2°C), Override, OSCAT ACTUATOR_PUMP, Runtime NON-RETAIN

### Python Scripts
- **heizung3.py v3.8.3** - Monitoring (manuell)
  - Grafische DI/DO-Anzeige
  - Runtime pro Pumpe
  - Override-Steuerung
  - LED-Test
  
- **heizung2.py v3.9.1** - Datenlogger (Cron)
  - MySQL Schema V7
  - Automatisches Schema-Management
  - Runtime + Cycles in DB
  - MQTT-Integration

- **reset_runtime.py** - Runtime zurücksetzen

## Installation

### SPS
```bash
# In CoDeSys 2.3:
# 1. Importiere heizung_v6.4.8_globals.txt
# 2. Importiere heizung_v6.4.8.st
# 3. Kompilieren & Hochladen
```

### Python
```bash
pip3 install pymodbus pymysql paho-mqtt sqlalchemy pandas --break-system-packages
chmod +x heizung2.py heizung3.py reset_runtime.py
```

### Cron-Job
```bash
# Alle 60 Sekunden
* * * * * ~/wago750-881/heizung2.py >> /var/log/heizung.log 2>&1
```

## Verwendung

```bash
# Monitoring
./heizung3.py

# Runtime zurücksetzen
./reset_runtime.py
```

## Modbus-Register

| Adresse | Inhalt |
|---------|--------|
| 12320-12352 | Sensor-Daten |
| 12336-12346 | Runtime/Cycles |
| 12348-12352 | Reason Bytes |
| 12412-12416 | Overrides |
| 512 | %QB0 (Physische Ausgänge) |

## Versionen

- **SPS**: v6.4.8
- **heizung3.py**: v3.8.3
- **heizung2.py**: v3.9.1
- **DB Schema**: V7

## Lizenz

MIT License

## Autor

[gerontec](https://github.com/gerontec)
EOF
    echo "✓ README.md erstellt"
else
    echo "✓ README.md vorhanden"
fi

# Erstelle .gitignore
if [ ! -f .gitignore ]; then
    echo "Erstelle .gitignore..."
    cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*.pyc
.Python

# Logs
*.log

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store

# Backup
*.bak
*~

# CoDeSys
*.opt
*.bak
*.prj~
EOF
    echo "✓ .gitignore erstellt"
else
    echo "✓ .gitignore vorhanden"
fi
echo ""

# Stage alle Dateien
echo "Stage Dateien..."
git add .
echo "✓ Alle Dateien gestaged"
echo ""

# Status
echo "Git Status:"
git status --short
echo ""

# Commit
read -p "Commit erstellen? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    git commit -m "Initial commit - WAGO 750-881 Heizungssteuerung

- SPS v6.4.8: ΔT-Regel (≥2°C), Override, Runtime NON-RETAIN
- Python v3.8.3 (heizung3.py - Monitoring)
- Python v3.9.1 (heizung2.py - Datenlogger)
- MySQL Schema V7 mit Runtime
- OSCAT ACTUATOR_PUMP Integration
- Grafische DI/DO-Anzeige
"
    echo "✓ Commit erstellt"
    echo ""
fi

echo "========================================="
echo "GitHub Repository erstellen"
echo "========================================="
echo ""
echo "1. Gehe zu: https://github.com/new"
echo ""
echo "   Repository name: $REPO_NAME"
echo "   Description: WAGO 750-881 Heizungssteuerung"
echo "   Visibility: Public"
echo ""
echo "   ⚠️ Wichtig: OHNE README/.gitignore/License"
echo ""
echo "2. Repository erstellt?"
read -p "   Weiter? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "Später fortfahren mit:"
    echo "  cd ~/wago750-881"
    echo "  git remote add origin git@github.com:${GITHUB_USER}/${REPO_NAME}.git"
    echo "  git push -u origin main"
    exit 0
fi

echo ""
echo "Füge Remote hinzu..."
if git remote get-url origin &>/dev/null; then
    echo "✓ Remote existiert bereits"
else
    git remote add origin git@github.com:${GITHUB_USER}/${REPO_NAME}.git
    echo "✓ Remote hinzugefügt"
fi

echo ""
echo "Push zu GitHub..."
git branch -M main
git push -u origin main

echo ""
echo "========================================="
echo "✅ Erfolgreich!"
echo "========================================="
echo ""
echo "Repository: https://github.com/${GITHUB_USER}/${REPO_NAME}"
echo ""
echo "Weitere Updates:"
echo "  cd ~/wago750-881"
echo "  git add ."
echo "  git commit -m 'Update'"
echo "  git push"
echo ""
