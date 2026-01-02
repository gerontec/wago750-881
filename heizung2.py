#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
================================================================================
HEIZUNGSSTEUERUNG - DATENLOGGER (heizung2.py)
================================================================================
VERSION: 3.9.0
DATUM: 02.01.2026 08:00:00
ÄNDERUNGEN: 
- NEU: Runtime-Anzeige aus OSCAT ACTUATOR_PUMP (MW32+24,25,26)
- NEU: Grafische DO-Anzeige (wie DI-Zeile)
- UPDATE: Reason Bytes verschoben auf MW32+30,31,32 (nach Seriennummer)
- UPDATE: Unterstützung für v6.4.8 (ΔT ≥ 2.0°C Regel)
- FIX: Physische Ausgänge aus %QB0 (Modbus 512)
================================================================================
"""
import sys
import pandas as pd
from datetime import datetime
from pymodbus.client import ModbusTcpClient
from sqlalchemy import create_engine, text
import paho.mqtt.client as mqtt
import time
import struct

# --- KONFIGURATION ---
SPS_IP = '192.168.178.2'
MQTT_BROKER = 'localhost'
MQTT_TOPIC = 'Node3/pin4'
MQTT_TIMEOUT = 5
DB_URL = 'mysql+pymysql://gh:a12345@10.8.0.1/wagodb?charset=utf8mb4'
SCHEMA_VERSION = 7  # Version erhöht für Runtime

# Modbus-Adressen (NEUE POSITIONEN nach v6.4.8!)
ADDR_REASON_WW = 12348  # xNewVar70[30]
ADDR_REASON_HK = 12350  # xNewVar70[31]
ADDR_REASON_BR = 12352  # xNewVar70[32]
ADDR_RUNTIME_WW = 12336  # xNewVar70[24] - Runtime in 0.01h
ADDR_RUNTIME_HK = 12338  # xNewVar70[25]
ADDR_RUNTIME_BR = 12340  # xNewVar70[26]
ADDR_CYCLES_WW = 12342   # xNewVar70[27]
ADDR_CYCLES_HK = 12344   # xNewVar70[28]
ADDR_CYCLES_BR = 12346   # xNewVar70[29]
ADDR_QB0 = 512           # Physische Ausgänge %QB0

# Globale MQTT-Variable
mqtt_temp = None
mqtt_received = False

def on_message(client, userdata, msg):
    global mqtt_temp, mqtt_received
    try:
        mqtt_temp = float(msg.payload.decode())
        mqtt_received = True
    except:
        mqtt_temp = None

def get_mqtt():
    global mqtt_temp, mqtt_received
    mqtt_temp, mqtt_received = None, False
    try:
        client = mqtt.Client()
        client.on_message = on_message
        client.connect(MQTT_BROKER, 1883, 60)
        client.subscribe(MQTT_TOPIC)
        start = time.time()
        client.loop_start()
        while not mqtt_received and (time.time() - start) < MQTT_TIMEOUT:
            time.sleep(0.1)
        client.loop_stop()
        client.disconnect()
        return mqtt_temp if mqtt_received else None
    except:
        return None

# Sensor-Formeln
calc_pt1000 = lambda r: round((r - 7134) / 25, 2) if 4000 < r < 25000 else 0.0
calc_boiler = lambda r: round((40536 - r) / 303.1, 2) if 4000 < r < 45000 else 0.0
calc_solar = lambda r: round((r - 26402) / 60, 2) if 4000 < r < 40000 else 0.0

def get_dint(registers, index):
    """Extrahiert DINT aus Register-Array (LOW, HIGH)"""
    low = registers[index * 2]
    high = registers[index * 2 + 1]
    value = (high << 16) | low
    return value - 0x100000000 if value >= 0x80000000 else value

def sanitize_reason_byte(value):
    """Bereinigt Reason-Byte Werte für TINYINT UNSIGNED (0-255)"""
    if value < 0:
        return value & 0xFF
    elif value > 255:
        return value & 0xFF
    else:
        return value

def read_reason_bytes(client):
    """Liest alle drei Reason Bytes - NEUE ADRESSEN!"""
    try:
        result = client.read_holding_registers(ADDR_REASON_WW, 6, slave=0)
        if not result.isError():
            ww = sanitize_reason_byte(get_dint(result.registers, 0))
            hk = sanitize_reason_byte(get_dint(result.registers, 1))
            br = sanitize_reason_byte(get_dint(result.registers, 2))
            return (ww, hk, br)
    except Exception as e:
        print(f"⚠ Reason Bytes Lesefehler: {e}")
    return (0, 0, 0)

def read_pump_runtime(client):
    """Liest Runtime und Cycles aus OSCAT ACTUATOR_PUMP"""
    try:
        result = client.read_holding_registers(ADDR_RUNTIME_WW, 12, slave=0)
        if not result.isError():
            ww_runtime_01h = get_dint(result.registers, 0)
            hk_runtime_01h = get_dint(result.registers, 1)
            br_runtime_01h = get_dint(result.registers, 2)
            ww_cycles = get_dint(result.registers, 3)
            hk_cycles = get_dint(result.registers, 4)
            br_cycles = get_dint(result.registers, 5)
            
            return {
                'ww_hours': ww_runtime_01h / 100.0,
                'hk_hours': hk_runtime_01h / 100.0,
                'br_hours': br_runtime_01h / 100.0,
                'ww_cycles': ww_cycles,
                'hk_cycles': hk_cycles,
                'br_cycles': br_cycles
            }
    except Exception as e:
        print(f"⚠ Runtime Lesefehler: {e}")
    return None

def read_physical_outputs(client):
    """Liest physische Ausgänge aus %QB0 (Adresse 512)"""
    try:
        result = client.read_holding_registers(ADDR_QB0, 1, slave=0)
        if not result.isError():
            output_byte = result.registers[0] & 0xFF
            return {
                'ww': bool(output_byte & 0x02),  # Bit 1
                'hk': bool(output_byte & 0x04),  # Bit 2
                'br': bool(output_byte & 0x08),  # Bit 3
                'qb0': output_byte
            }
    except Exception as e:
        print(f"⚠ Physische Ausgänge Lesefehler: {e}")
    return None

def decode_reason_ww(r):
    """WW-Pumpe: v6.4.8 vereinfacht - nur ΔT ≥ 2.0°C"""
    KNOWN_BITS = 0x01
    if r & ~KNOWN_BITS:
        return "ACTUATOR"
    if r & 0x01:
        return "ΔT≥2°C"
    return "ΔT<2°C"

def decode_reason_hk(r):
    """HK-Pumpe: Bitweise"""
    KNOWN_BITS = 0x07
    if r & ~KNOWN_BITS:
        return "ACTUATOR"
    if r == 0:
        return "Aus"
    parts = []
    if r & 0x01:
        parts.append("Frost")
    if r & 0x02:
        parts.append("Wärme")
    if r & 0x04:
        parts.append("Override")
    return "+".join(parts)

def decode_reason_br(r):
    """Brunnenpumpe: Bit 0 = HK aktiv"""
    KNOWN_BITS = 0x01
    if r & ~KNOWN_BITS:
        return "ACTUATOR"
    return "HK aktiv" if r & 0x01 else "HK inaktiv"

def decode_di8_word(di_word):
    """Dekodiert das 16-Bit Word der 8-Kanal DI-Karte"""
    return {
        'di_0': bool(di_word & 0x01),
        'di_1': bool(di_word & 0x02),
        'di_2': bool(di_word & 0x04),
        'di_3': bool(di_word & 0x08),
        'di_4': bool(di_word & 0x10),
        'di_5': bool(di_word & 0x20),
        'di_6': bool(di_word & 0x40),
        'di_7': bool(di_word & 0x80),
        'raw_value': di_word
    }

def format_runtime(hours):
    """Formatiert Runtime in Tagen und Stunden"""
    total_hours = int(hours)
    days = total_hours // 24
    hrs = total_hours % 24
    return f"{days}d {hrs:02d}h"

def read_di8_card(client):
    """Liest die 8-Kanal Digital-Input-Karte (Input Register 4)"""
    try:
        result = client.read_input_registers(4, 1, slave=0)
        if not result.isError():
            return result.registers[0]
    except Exception as e:
        print(f"⚠ DI-8-Karte Lesefehler: {e}")
    return None

def ensure_schema(engine):
    """Erstellt/aktualisiert Datenbank-Schema"""
    with engine.begin() as conn:
        # Prüfe ob schema_version Tabelle existiert
        table_exists = conn.execute(text("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema='wagodb' AND table_name='schema_version'
        """)).scalar()
        
        # Versions-Tabelle erstellen falls nicht vorhanden
        if not table_exists:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    version INT NOT NULL,
                    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    description VARCHAR(255),
                    INDEX idx_version (version)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            current_version = 0
        else:
            current_version = conn.execute(text("""
                SELECT COALESCE(MAX(version), 0) FROM schema_version
            """)).scalar()
        
        if current_version >= SCHEMA_VERSION:
            print(f"✓ Schema aktuell (V{current_version})")
            return
        
        print(f"→ Schema-Update V{current_version} → V{SCHEMA_VERSION}")
        
        # Haupt-Tabelle erstellen/erweitern
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS heizung (
                id INT AUTO_INCREMENT PRIMARY KEY,
                version DECIMAL(3,1) NOT NULL DEFAULT 1.2,
                sensor_gruppe CHAR(1) NOT NULL DEFAULT 'B',
                zeitstempel DATETIME NOT NULL,
                stunde TINYINT NOT NULL,
                zaehler_kwh INT UNSIGNED NOT NULL DEFAULT 0,
                zaehler_pumpe INT UNSIGNED NOT NULL DEFAULT 0,
                zaehler_brunnen INT UNSIGNED NOT NULL DEFAULT 0,
                raw_vorlauf SMALLINT UNSIGNED NOT NULL,
                raw_aussen SMALLINT UNSIGNED NOT NULL,
                raw_innen SMALLINT UNSIGNED NOT NULL,
                raw_kessel SMALLINT UNSIGNED NOT NULL,
                temp_vorlauf DECIMAL(5,2) NOT NULL,
                temp_aussen DECIMAL(5,2) NOT NULL,
                temp_innen DECIMAL(5,2) NOT NULL,
                temp_kessel DECIMAL(5,2) NOT NULL,
                raw_warmwasser SMALLINT UNSIGNED NOT NULL,
                temp_warmwasser DECIMAL(5,2) NOT NULL,
                wert_oeltank DECIMAL(7,2) NOT NULL,
                raw_ruecklauf SMALLINT UNSIGNED NOT NULL,
                temp_ruecklauf DECIMAL(5,2) NOT NULL,
                raw_solar SMALLINT UNSIGNED NOT NULL,
                temp_solar DECIMAL(5,2) NOT NULL,
                ky9a DECIMAL(5,2) DEFAULT NULL,
                status_word SMALLINT UNSIGNED NOT NULL,
                INDEX idx_zeitstempel (zeitstempel),
                INDEX idx_stunde (stunde)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))
        
        # Spalte ky9a hinzufügen falls nicht vorhanden (V4)
        if current_version < 4:
            try:
                conn.execute(text("""
                    ALTER TABLE heizung ADD COLUMN ky9a DECIMAL(5,2) DEFAULT NULL 
                    COMMENT 'MQTT Node3/pin4' AFTER temp_solar
                """))
                print("  ✓ Spalte ky9a hinzugefügt")
            except Exception as e:
                if "Duplicate column" not in str(e):
                    print(f"  ⚠ ky9a: {e}")
        
        # Spalte di8_raw hinzufügen falls nicht vorhanden (V5)
        if current_version < 5:
            try:
                conn.execute(text("""
                    ALTER TABLE heizung ADD COLUMN di8_raw SMALLINT UNSIGNED DEFAULT NULL 
                    COMMENT '8-Kanal DI-Karte Raw-Wert' AFTER status_word
                """))
                print("  ✓ Spalte di8_raw hinzugefügt")
            except Exception as e:
                if "Duplicate column" not in str(e):
                    print(f"  ⚠ di8_raw: {e}")
        
        # Reason Bytes hinzufügen (V6)
        if current_version < 6:
            try:
                conn.execute(text("""
                    ALTER TABLE heizung 
                    ADD COLUMN reason_ww TINYINT UNSIGNED DEFAULT 0 COMMENT 'WW-Pumpe Reason' AFTER di8_raw,
                    ADD COLUMN reason_hk TINYINT UNSIGNED DEFAULT 0 COMMENT 'HK-Pumpe Reason' AFTER reason_ww,
                    ADD COLUMN reason_br TINYINT UNSIGNED DEFAULT 0 COMMENT 'Brunnenpumpe Reason' AFTER reason_hk
                """))
                print("  ✓ Spalten reason_ww, reason_hk, reason_br hinzugefügt")
            except Exception as e:
                if "Duplicate column" not in str(e):
                    print(f"  ⚠ Reason Bytes: {e}")
        
        # Runtime Spalten hinzufügen (V7)
        if current_version < 7:
            try:
                conn.execute(text("""
                    ALTER TABLE heizung 
                    ADD COLUMN runtime_ww_h DECIMAL(6,2) DEFAULT 0 COMMENT 'WW Runtime Stunden' AFTER reason_br,
                    ADD COLUMN runtime_hk_h DECIMAL(6,2) DEFAULT 0 COMMENT 'HK Runtime Stunden' AFTER runtime_ww_h,
                    ADD COLUMN runtime_br_h DECIMAL(6,2) DEFAULT 0 COMMENT 'BR Runtime Stunden' AFTER runtime_hk_h,
                    ADD COLUMN cycles_ww INT UNSIGNED DEFAULT 0 COMMENT 'WW Zyklen' AFTER runtime_br_h,
                    ADD COLUMN cycles_hk INT UNSIGNED DEFAULT 0 COMMENT 'HK Zyklen' AFTER cycles_ww,
                    ADD COLUMN cycles_br INT UNSIGNED DEFAULT 0 COMMENT 'BR Zyklen' AFTER cycles_hk
                """))
                print("  ✓ Spalten runtime_*_h und cycles_* hinzugefügt")
            except Exception as e:
                if "Duplicate column" not in str(e):
                    print(f"  ⚠ Runtime: {e}")
        
        # Version speichern
        conn.execute(text("""
            INSERT INTO schema_version (version, description) 
            VALUES (:v, :desc)
        """), {'v': SCHEMA_VERSION, 'desc': f'Auto-Update auf V{SCHEMA_VERSION} mit Runtime'})
        
        print(f"✓ Schema-Update abgeschlossen (V{SCHEMA_VERSION})")

def run_sync():
    now = datetime.now()
    mqtt_val = get_mqtt()
    
    # Datenbank vorbereiten
    engine = create_engine(DB_URL, pool_pre_ping=True)
    ensure_schema(engine)
    
    # Modbus-Kommunikation
    client = ModbusTcpClient(SPS_IP, port=502, timeout=5)
    if not client.connect():
        print("✗ SPS-Verbindung fehlgeschlagen")
        sys.exit(1)
    
    try:
        # Reason Bytes lesen
        reason_ww, reason_hk, reason_br = read_reason_bytes(client)
        
        # Runtime lesen
        runtime = read_pump_runtime(client)
        
        # Physische Ausgänge lesen
        physical_out = read_physical_outputs(client)
        
        # DI-8-Karte lesen
        di8_raw = read_di8_card(client)
        if di8_raw is not None:
            di8_data = decode_di8_word(di8_raw)
            di_status = " ".join([f"DI{i}:{'■' if di8_data[f'di_{i}'] else '□'}" for i in range(8)])
        
        # DO-Status formatieren
        if physical_out:
            do_status = " ".join([
                f"DO0:{'■' if physical_out['qb0'] & 0x01 else '□'}",
                f"DO1(WW):{'■' if physical_out['ww'] else '□'}",
                f"DO2(HK):{'■' if physical_out['hk'] else '□'}",
                f"DO3(BR):{'■' if physical_out['br'] else '□'}",
                f"DO4:□",
                f"DO5:{'■' if physical_out['qb0'] & 0x20 else '□'}"
            ])
        
        client.write_register(12288, now.hour, slave=0)
        result = client.read_holding_registers(12320, 32, slave=0)
        if result.isError():
            return
        
        reg = result.registers
        get_val = lambda i: max(reg[i*2], reg[i*2+1])
        
        # Daten sammeln
        data = {
            'version': 1.2,
            'sensor_gruppe': 'A' if get_val(14) & 0x10 else 'B',
            'zeitstempel': now,
            'stunde': now.hour,
            'zaehler_kwh': get_val(0),
            'zaehler_pumpe': get_val(1),
            'zaehler_brunnen': get_val(2),
            'raw_vorlauf': (r_vl := get_val(4)),
            'raw_aussen': (r_at := get_val(5)),
            'raw_innen': (r_it := get_val(6)),
            'raw_kessel': (r_ke := get_val(7)),
            'temp_vorlauf': calc_pt1000(r_vl),
            'temp_aussen': calc_pt1000(r_at),
            'temp_innen': calc_pt1000(r_it),
            'temp_kessel': calc_pt1000(r_ke),
            'raw_warmwasser': (r_ww := get_val(8)),
            'temp_warmwasser': calc_boiler(r_ww),
            'wert_oeltank': float(get_val(9)),
            'raw_ruecklauf': (r_ru := get_val(10)),
            'temp_ruecklauf': calc_pt1000(r_ru),
            'raw_solar': (r_so := get_val(11)),
            'temp_solar': calc_solar(r_so),
            'ky9a': mqtt_val,
            'status_word': get_val(14),
            'di8_raw': di8_raw,
            'reason_ww': reason_ww,
            'reason_hk': reason_hk,
            'reason_br': reason_br,
            'runtime_ww_h': runtime['ww_hours'] if runtime else 0,
            'runtime_hk_h': runtime['hk_hours'] if runtime else 0,
            'runtime_br_h': runtime['br_hours'] if runtime else 0,
            'cycles_ww': runtime['ww_cycles'] if runtime else 0,
            'cycles_hk': runtime['hk_cycles'] if runtime else 0,
            'cycles_br': runtime['br_cycles'] if runtime else 0
        }
        
        # Log
        print("=" * 90)
        print(f"HEIZUNGSSTEUERUNG v3.9.0 | SPS: v6.4.8")
        print("=" * 90)
        print(f"Zeit: {now:%Y-%m-%d %H:%M:%S} | WAGO 750-881 (Schema V{SCHEMA_VERSION})")
        print(f"Zähler → kWh:{data['zaehler_kwh']} | Pumpe:{data['zaehler_pumpe']} | Brunnen:{data['zaehler_brunnen']}")
        print(f"Gruppe A → VL:{data['temp_vorlauf']}°C | AT:{data['temp_aussen']}°C | IT:{data['temp_innen']}°C | KE:{data['temp_kessel']}°C")
        print(f"Gruppe B → WW:{data['temp_warmwasser']}°C | Rück:{data['temp_ruecklauf']}°C | Solar:{data['temp_solar']}°C")
        print(f"MQTT Node3 → {mqtt_val}°C" if mqtt_val else "MQTT Node3 → N/A")
        if di8_raw is not None:
            print(f"DI: {di_status}")
        if physical_out:
            print(f"DO: {do_status} | %QB0=0x{physical_out['qb0']:02X}")
        print(f"Status → Phase:{data['sensor_gruppe']} | 0x{data['status_word']:04X}")
        print(f"Pumpen → WW:{'AN' if physical_out and physical_out['ww'] else 'AUS'} | HK:{'AN' if physical_out and physical_out['hk'] else 'AUS'} | BR:{'AN' if physical_out and physical_out['br'] else 'AUS'}")
        if runtime:
            print(f"Runtime → WW:{format_runtime(runtime['ww_hours'])} ({runtime['ww_cycles']}×) | HK:{format_runtime(runtime['hk_hours'])} ({runtime['hk_cycles']}×) | BR:{format_runtime(runtime['br_hours'])} ({runtime['br_cycles']}×)")
        print(f"Reason → WW:0x{reason_ww:02X} ({decode_reason_ww(reason_ww)}) | HK:0x{reason_hk:02X} ({decode_reason_hk(reason_hk)}) | BR:0x{reason_br:02X} ({decode_reason_br(reason_br)})")
        print("=" * 90)
        
        # In DB schreiben
        df = pd.DataFrame([data])
        df.to_sql('heizung', engine, if_exists='append', index=False)
        print("✓ Daten erfolgreich in DB gespeichert")
        
    except Exception as e:
        print(f"✗ Fehler: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()

if __name__ == "__main__":
    run_sync()
