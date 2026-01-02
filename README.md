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
