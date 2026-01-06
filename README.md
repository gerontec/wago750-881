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

# WAGO 750-881 Heizungssteuerung

Projekt für die Steuerung einer Heizung (WW, HK, Brunnen) mit einer WAGO 750-881 PLC.

## Modbus Register Mapping (Holding Registers, Slave 0)

### Messwerte (xMeasure[1..32]) – ab Adresse 12320 (%MW32 - %MW63)
- %MW32-35: Physische Analog Inputs %IW0-%IW3 (Raw 0-32767)
- %MW36: Digital Input %IW4 (DI8chan)
- %MW42: Status Word (Bit4=Mux Phase A/B, Bit5=Data Ready, Bit3=Nacht, Bit6=Sensor Error)
- %MW63: Physischer Output Byte %QB0

Sample & Hold + berechnete Werte siehe wagostatus.py.

### Sollwerte (xSetpoints[1..16]) – ab Adresse 12384 (%MW96 - %MW111)
- %MW100: Nacht Start/End
- %MW109: Frostschwelle, Tank-Temp usw.
- %MW112-115: Overrides

### System-Diagnose (xSystem[1..8]) – ab Adresse 12416 (%MW128 - %MW135)
- %MW128/129: Uptime (32-Bit)
- %MW130: Error Count
- %MW131: CPU Load %

## Skripte
- wagostatus.py: Vollständiger Status-Überblick (physische I/O + alle Variablen)
- heizung2.py / heizung3.py: Steuerlogik

Version: 1.1.0 (06.01.2026)
