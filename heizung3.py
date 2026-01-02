#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
================================================================================
HEIZUNGSSTEUERUNG - DATENLOGGER
================================================================================
VERSION: 3.7.3
DATUM: 01.01.2026 21:15:00
ÄNDERUNGEN: 
- TEST: DO6 LED-Test via FC15 (Write Coils) statt FC16
- Nutzt existierenden Modbus-Job in WAGO Config
- FIX: Pumpen-Status aus %QB0 via FC3 (Addr 512)
================================================================================
"""
import pymysql
import sys
from datetime import datetime
from pymodbus.client import ModbusTcpClient
import paho.mqtt.client as mqtt
import time
import struct
from dataclasses import dataclass
from typing import Optional, Dict, List

VERSION = {
    'major': 3,
    'minor': 8,
    'patch': 3,
    'string': 'v3.8.3',
    'date': '02.01.2026',
    'time': '08:20:00',
    'description': 'FIX: Spalte version jetzt dynamisch aus SPS (z.B. 6.4)'
}

def print_version():
    """Gibt Versionsinformation aus"""
    print("=" * 80)
    print(f"HEIZUNGSSTEUERUNG {VERSION['string']}")
    print(f"Build: {VERSION['date']} {VERSION['time']}")
    print(f"Info: {VERSION['description']}")
    print("=" * 80)

@dataclass
class Config:
    """Zentrale Konfiguration"""
    WW_PUMPE_OVERRIDE: int = 0
    HK_PUMPE_OVERRIDE: int = 0
    BRUNNEN_OVERRIDE: int = -1
    
    ADDR_WW_PUMPE: int = 12412
    ADDR_HK_PUMPE: int = 12414
    ADDR_BRUNNEN: int = 12416
    
    ADDR_REASON_WW: int = 12348
    ADDR_REASON_HK: int = 12350
    ADDR_REASON_BR: int = 12352
    
    SPS_IP: str = '192.168.178.2'
    SPS_PORT: int = 502
    SPS_TIMEOUT: int = 5
    
    MQTT_BROKER: str = 'localhost'
    MQTT_PORT: int = 1883
    MQTT_TOPIC: str = 'Node3/pin4'
    MQTT_TIMEOUT: int = 5
    
    DB_CONFIG: dict = None
    
    def __post_init__(self):
        if self.DB_CONFIG is None:
            self.DB_CONFIG = {
                'host': '10.8.0.1',
                'user': 'gh',
                'password': 'a12345',
                'database': 'wagodb',
                'charset': 'utf8mb4'
            }

CONFIG = Config()

@dataclass
class SensorData:
    """Sensor-Rohdaten und berechnete Werte"""
    raw_vl: int = 0
    raw_at: int = 0
    raw_it: int = 0
    raw_ke: int = 0
    raw_ww: int = 0
    raw_ot: int = 0
    raw_ru: int = 0
    raw_so: int = 0
    
    temp_vl: float = 0.0
    temp_at: float = 0.0
    temp_it: float = 0.0
    temp_ke: float = 0.0
    temp_ww: float = 0.0
    temp_ru: float = 0.0
    temp_so: float = 0.0
    temp_ot: float = 0.0
    
    mqtt_temp: Optional[float] = None

@dataclass
class StatusData:
    """System-Status"""
    ww_pumpe: bool = False
    hz_pumpe: bool = False
    brunnen: bool = False
    ww_pumpe_modbus: bool = False
    hz_pumpe_modbus: bool = False
    brunnen_modbus: bool = False
    pumpe_signal: bool = False
    phase_a: bool = False
    data_ready: bool = False
    phase: str = 'A'
    reason_ww: int = 0
    reason_hk: int = 0
    reason_br: int = 0
    reason_ww_text: str = ""
    reason_hk_text: str = ""
    reason_br_text: str = ""

@dataclass
class PumpRuntime:
    """Pumpen Betriebsdaten"""
    ww_hours: float = 0.0
    hk_hours: float = 0.0
    br_hours: float = 0.0
    ww_cycles: int = 0
    hk_cycles: int = 0
    br_cycles: int = 0

@dataclass
class SystemDiagnostics:
    """System-Diagnose"""
    uptime_sec: int = 0
    error_count: int = 0
    cpu_load: int = 0
    cycle_min_us: int = 0
    cycle_max_us: int = 0
    cycle_avg_us: int = 0

@dataclass
class SPSVersion:
    """SPS Programmversion"""
    major: int = 0
    minor: int = 0
    patch: int = 0
    serial: int = 0
    version_string: str = "v0.0.0"

def calc_pt1000(raw: int) -> float:
    """PT1000 Sensor Berechnung"""
    if not (4000 <= raw <= 25000):
        return 0.0
    return round((float(raw) - 7134.0) / 25.0, 2)

def calc_ntc_solar(raw: int) -> float:
    """NTC Solar Sensor Berechnung"""
    if not (4000 <= raw <= 40000):
        return 0.0
    return round((float(raw) - 26402.0) / 60.0, 2)

def calc_boiler(raw: int) -> float:
    """NTC Boiler Sensor Berechnung"""
    if not (4000 <= raw <= 45000):
        return 0.0
    return round((40536.0 - float(raw)) / 303.1, 2)

def decode_reason_ww(reason: int) -> str:
    """Dekodiert WW-Pumpe Reason Byte (v6.4.8: nur ΔT ≥ 2.0°C)"""
    KNOWN_BITS = 0x01  # Nur noch Bit 0 für ΔT
    
    if reason & ~KNOWN_BITS:
        return f"0x{reason:02X} - ACTUATOR-Logik (MIN_ONTIME/RUN_EVERY)"
    
    if reason & 0x01:
        return f"0x{reason:02X} - ΔT ≥ 2.0°C → AN"
    elif reason == 0:
        return "0x00 - ΔT < 2.0°C → AUS"
    else:
        return f"0x{reason:02X} - Unbekannt"

def decode_reason_hk(reason: int) -> str:
    """Dekodiert HK-Pumpe Reason Byte"""
    KNOWN_BITS = 0x07
    
    if reason & ~KNOWN_BITS:
        return f"0x{reason:02X} - ACTUATOR-Logik (MIN_ONTIME/MIN_OFFTIME/RUN_EVERY)"
    
    reasons = []
    if reason & 0x01:
        reasons.append("Frostschutz(AT<3°C)")
    if reason & 0x02:
        reasons.append("Wärmebedarf")
    if reason & 0x04:
        reasons.append("Override")
    
    if reason == 0:
        return "0x00 - AUS (keine Anforderung)"
    else:
        return f"0x{reason:02X} - " + ", ".join(reasons)

def decode_reason_br(reason: int) -> str:
    """Dekodiert Brunnenpumpe Reason Byte"""
    KNOWN_BITS = 0x01
    
    if reason & ~KNOWN_BITS:
        return f"0x{reason:02X} - ACTUATOR-Logik (MIN_ONTIME/RUN_EVERY)"
    
    if reason & 0x01:
        return f"0x{reason:02X} - HK aktiv"
    elif reason == 0:
        return "0x00 - HK inaktiv"
    else:
        return f"0x{reason:02X} - Unbekannt"

class ModbusHelper:
    """Hilfsklasse für Modbus-Operationen"""
    
    @staticmethod
    def write_dint(client: ModbusTcpClient, address: int, value: int, 
                   pump_name: str = "") -> bool:
        """Schreibt einen DINT (32-bit signed)"""
        try:
            payload = struct.pack('>i', value)
            registers = struct.unpack('>HH', payload)
            result = client.write_registers(address, registers, slave=0)
            if not result.isError():
                if pump_name:
                    print(f"✓ {pump_name} (MW{address}) → {value}")
                return True
            return False
        except Exception as e:
            print(f"✗ Fehler beim Schreiben MW{address}: {e}")
            return False
    
    @staticmethod
    def get_dint(registers: list, index: int) -> int:
        """Extrahiert DINT aus Register-Array"""
        low = registers[index * 2]
        high = registers[index * 2 + 1]
        value = (high << 16) | low
        if value >= 0x80000000:
            value -= 0x100000000
        return value
    
    @staticmethod
    def get_max_word(registers: list, index: int) -> int:
        """Holt Maximum aus DINT"""
        return max(registers[index * 2], registers[index * 2 + 1])

class MQTTTemperature:
    """MQTT Temperatur-Leser"""
    
    def __init__(self, broker: str, port: int, topic: str, timeout: int):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.timeout = timeout
        self.value: Optional[float] = None
        self.received = False
    
    def _on_message(self, client, userdata, msg):
        try:
            self.value = float(msg.payload.decode())
            self.received = True
        except:
            self.value = None
    
    def read(self) -> Optional[float]:
        """Liest Temperatur von MQTT"""
        self.value = None
        self.received = False
        
        try:
            client = mqtt.Client()
            client.on_message = self._on_message
            client.connect(self.broker, self.port, 60)
            client.subscribe(self.topic)
            
            start_time = time.time()
            client.loop_start()
            
            while not self.received and (time.time() - start_time) < self.timeout:
                time.sleep(0.1)
            
            client.loop_stop()
            client.disconnect()
            
            return self.value if self.received else None
            
        except Exception as e:
            print(f"✗ MQTT Fehler: {e}")
            return None

def decode_di8_word(di_word: int) -> Dict:
    """Dekodiert DI-Karte"""
    return {
        **{f'di_{i}': bool(di_word & (1 << i)) for i in range(8)},
        'raw_value': di_word
    }

def format_di8_status(di_data: Dict) -> str:
    """Formatiert DI-Status"""
    return " ".join(
        f"DI{i}:{'■' if di_data[f'di_{i}'] else '□'}" 
        for i in range(8)
    )

def format_do_status(ww: bool, hk: bool, br: bool, status_word: int) -> str:
    """Formatiert DO-Status aus physischen Ausgängen und Status Word"""
    # Extrahiere DO-Bits aus Status Word
    mux = bool(status_word & 0x10)  # Phase A (Mux)
    o5 = bool(status_word & 0x10)   # O5 = Mux
    
    outputs = [
        ('DO0(Mux)', mux),
        ('DO1(WW)', ww),
        ('DO2(HK)', hk),
        ('DO3(BR)', br),
        ('DO4', False),  # Ungenutzt
        ('DO5(Mux)', o5)
    ]
    
    return " ".join(
        f"{name}:{'■' if state else '□'}" 
        for name, state in outputs
    )

def decode_status_word(status_word: int, coil_ww: bool, coil_hk: bool, coil_br: bool,
                      reason_ww: int = 0, reason_hk: int = 0, reason_br: int = 0) -> StatusData:
    """Dekodiert Status-Word und verwendet physische Ausgänge"""
    return StatusData(
        # PHYSISCHE AUSGÄNGE (aus COILS) - DIE WAHRHEIT!
        ww_pumpe=coil_ww,
        hz_pumpe=coil_hk,
        brunnen=coil_br,
        # MODBUS STATUS (kann abweichen!)
        ww_pumpe_modbus=bool(status_word & 0x01),
        hz_pumpe_modbus=bool(status_word & 0x02),
        brunnen_modbus=bool(status_word & 0x04),
        # REST
        pumpe_signal=bool(status_word & 0x08),
        phase_a=bool(status_word & 0x10),
        data_ready=bool(status_word & 0x20),
        phase='A' if (status_word & 0x10) else 'B',
        reason_ww=reason_ww,
        reason_hk=reason_hk,
        reason_br=reason_br,
        reason_ww_text=decode_reason_ww(reason_ww),
        reason_hk_text=decode_reason_hk(reason_hk),
        reason_br_text=decode_reason_br(reason_br)
    )

def decode_alarm_word(alarm_word: int) -> List[str]:
    """Dekodiert Alarme"""
    alarm_map = {
        0x01: "Vorlauf zu heiß",
        0x02: "Vorlauf zu kalt",
        0x04: "Sensor-Fehler Vorlauf",
        0x08: "Sensor-Fehler Außen",
        0x10: "Sensor-Fehler Innen",
        0x20: "Sensor-Fehler Kessel",
        0x40: "Sensor-Fehler Warmwasser",
        0x80: "Sensor-Fehler Rücklauf",
        0x100: "Sensor-Fehler Solar",
        0x200: "Watchdog Fehler",
        0x400: "Modbus Fehler",
        0x800: "Überlastung CPU"
    }
    return [msg for bit, msg in alarm_map.items() if alarm_word & bit]

def format_uptime(seconds: int) -> str:
    """Formatiert Uptime"""
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    return f"{days}d {hours:02d}:{minutes:02d}"

def format_runtime(hours: float) -> str:
    """Formatiert Runtime in Tagen und Stunden"""
    total_hours = int(hours)
    days = total_hours // 24
    hrs = total_hours % 24
    return f"{days}d {hrs:02d}h"

class SPSReader:
    """Liest alle Daten von der SPS"""
    
    def __init__(self, client: ModbusTcpClient):
        self.client = client
        self.helper = ModbusHelper()
    
    def wait_for_data_ready(self, max_retries: int = 10) -> bool:
        """Wartet auf Data-Ready"""
        for retry in range(max_retries):
            result = self.client.read_holding_registers(12320, 32, slave=0)
            if result.isError():
                return False
            
            status_word = result.registers[14 * 2]
            if status_word & 0x20:
                return True
            
            print(f"⚠ SPS schaltet um. Warte... ({retry+1}/{max_retries})")
            time.sleep(1.2)
        
        return False
    
    def read_sensors(self, registers: list) -> SensorData:
        """Liest Sensor-Werte"""
        get_val = lambda idx: self.helper.get_max_word(registers, idx)
        
        data = SensorData()
        data.raw_vl = get_val(4)
        data.raw_at = get_val(5)
        data.raw_it = get_val(6)
        data.raw_ke = get_val(7)
        data.raw_ww = get_val(8)
        data.raw_ot = get_val(9)
        data.raw_ru = get_val(10)
        data.raw_so = get_val(11)
        
        data.temp_vl = calc_pt1000(data.raw_vl)
        data.temp_at = calc_pt1000(data.raw_at)
        data.temp_it = calc_pt1000(data.raw_it)
        data.temp_ke = calc_pt1000(data.raw_ke)
        data.temp_ww = calc_boiler(data.raw_ww)
        data.temp_ru = calc_pt1000(data.raw_ru)
        data.temp_so = calc_ntc_solar(data.raw_so)
        data.temp_ot = float(data.raw_ot)
        
        return data
    
    def read_reason_bytes(self) -> tuple:
        """Liest Reason Bytes"""
        try:
            result = self.client.read_holding_registers(CONFIG.ADDR_REASON_WW, 6, slave=0)
            if not result.isError():
                reason_ww = self.helper.get_dint(result.registers, 0) & 0xFF
                reason_hk = self.helper.get_dint(result.registers, 1) & 0xFF
                reason_br = self.helper.get_dint(result.registers, 2) & 0xFF
                
                print(f"✓ Reason Bytes:")
                print(f"  WW: {reason_ww} (0x{reason_ww:02X})")
                print(f"  HK: {reason_hk} (0x{reason_hk:02X})")
                print(f"  BR: {reason_br} (0x{reason_br:02X})")
                
                return (reason_ww, reason_hk, reason_br)
        except Exception as e:
            print(f"⚠ Fehler Reason Bytes: {e}")
        return (0, 0, 0)
    
    def read_pump_runtime(self) -> Optional[PumpRuntime]:
        """Liest Pumpen Runtime und Cycles aus OSCAT ACTUATOR_PUMP"""
        try:
            # MW32+24,25,26 = Runtime in 0.01h
            # MW32+27,28,29 = Cycles
            result = self.client.read_holding_registers(12320, 64, slave=0)
            if not result.isError():
                # Runtime in 0.01h → Stunden
                ww_runtime_01h = self.helper.get_dint(result.registers, 24)
                hk_runtime_01h = self.helper.get_dint(result.registers, 25)
                br_runtime_01h = self.helper.get_dint(result.registers, 26)
                
                # Cycles
                ww_cycles = self.helper.get_dint(result.registers, 27)
                hk_cycles = self.helper.get_dint(result.registers, 28)
                br_cycles = self.helper.get_dint(result.registers, 29)
                
                print(f"✓ Pumpen Runtime:")
                print(f"  WW: {ww_runtime_01h / 100.0:.2f}h ({ww_cycles} Zyklen)")
                print(f"  HK: {hk_runtime_01h / 100.0:.2f}h ({hk_cycles} Zyklen)")
                print(f"  BR: {br_runtime_01h / 100.0:.2f}h ({br_cycles} Zyklen)")
                
                return PumpRuntime(
                    ww_hours=ww_runtime_01h / 100.0,
                    hk_hours=hk_runtime_01h / 100.0,
                    br_hours=br_runtime_01h / 100.0,
                    ww_cycles=ww_cycles,
                    hk_cycles=hk_cycles,
                    br_cycles=br_cycles
                )
        except Exception as e:
            print(f"⚠ Fehler Pump Runtime: {e}")
        return None
    
    def test_digital_output_write(self) -> bool:
        """
        Testet FC15 Write Coils: Setzt %QX0.5 (Bit 5) auf TRUE
        LED-Test für Ausgang 5 (letzter verfügbarer DO)
        """
        try:
            # Lese aktuellen Zustand via FC3
            result = self.client.read_holding_registers(512, 1, slave=0)
            if result.isError():
                print("✗ Fehler beim Lesen von %QB0")
                return False
            
            current_byte = result.registers[0] & 0xFF
            print(f"✓ Aktueller %QB0: 0x{current_byte:02X} (Binär: {current_byte:08b})")
            
            # Erstelle Coil-Array (nur 6 Bits, da nur 6 DOs vorhanden!)
            coils = []
            for i in range(6):  # Nur 0-5!
                coils.append(bool(current_byte & (1 << i)))
            
            # Setze Bit 5 (DO5, %QX0.5 - letzter verfügbarer Ausgang!)
            coils[5] = True
            
            print(f"✓ Schreibe 6 Coils: {coils}")
            
            # Schreibe mit FC15 (Write Multiple Coils) ab Adresse 512
            write_result = self.client.write_coils(512, coils, slave=0)
            
            if not write_result.isError():
                print(f"✓ FC15 Write erfolgreich (DO5 = Bit 5 ON)")
                
                # Verifizieren via FC3
                time.sleep(0.2)
                verify = self.client.read_holding_registers(512, 1, slave=0)
                if not verify.isError():
                    verify_byte = verify.registers[0] & 0xFF
                    print(f"✓ Verifiziert via FC3: 0x{verify_byte:02X} (Binär: {verify_byte:08b})")
                    
                    if verify_byte & 0x20:  # Bit 5
                        print("✅ DO5 LED sollte jetzt leuchten!")
                        return True
                    else:
                        print("⚠️ DO5 wurde nicht gesetzt!")
                        return False
            else:
                print(f"✗ Fehler beim Schreiben: {write_result}")
                return False
                
        except Exception as e:
            print(f"✗ Exception: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        return False

    def read_physical_outputs(self) -> tuple:
        """Liest physische Ausgänge aus %QB0 (Adresse 512) - DIE WAHRHEIT!"""
        try:
            # FC3: Read Holding Register ab Adresse 512 (%QB0)
            result = self.client.read_holding_registers(512, 1, slave=0)
            if not result.isError():
                output_byte = result.registers[0] & 0xFF  # Nur Low-Byte
                
                # Bit-Extraktion:
                # Bit 0 = %QX0.0 (Output_0/Mux)
                # Bit 1 = %QX0.1 (O1_WWPump)
                # Bit 2 = %QX0.2 (O2_UmwaelzHK1)
                # Bit 3 = %QX0.3 (O3_Brunnen)
                ww = bool(output_byte & 0x02)  # Bit 1
                hk = bool(output_byte & 0x04)  # Bit 2
                br = bool(output_byte & 0x08)  # Bit 3
                
                print(f"✓ Physische Ausgänge (%QB0=0x{output_byte:02X}): WW={ww}, HK={hk}, BR={br}")
                return (ww, hk, br)
        except Exception as e:
            print(f"⚠ Fehler Physische Ausgänge: {e}")
        return (False, False, False)
        """Liest physische Ausgänge aus %QB0 (Adresse 512) - DIE WAHRHEIT!"""
        try:
            # FC3: Read Holding Register ab Adresse 512 (%QB0)
            result = self.client.read_holding_registers(512, 1, slave=0)
            if not result.isError():
                output_byte = result.registers[0] & 0xFF  # Nur Low-Byte
                
                # Bit-Extraktion:
                # Bit 0 = %QX0.0 (Output_0/Mux)
                # Bit 1 = %QX0.1 (O1_WWPump)
                # Bit 2 = %QX0.2 (O2_UmwaelzHK1)
                # Bit 3 = %QX0.3 (O3_Brunnen)
                ww = bool(output_byte & 0x02)  # Bit 1
                hk = bool(output_byte & 0x04)  # Bit 2
                br = bool(output_byte & 0x08)  # Bit 3
                
                print(f"✓ Physische Ausgänge (%QB0=0x{output_byte:02X}): WW={ww}, HK={hk}, BR={br}")
                return (ww, hk, br)
        except Exception as e:
            print(f"⚠ Fehler Physische Ausgänge: {e}")
        return (False, False, False)
    
    def read_di8_card(self) -> Optional[Dict]:
        """Liest DI-Karte"""
        try:
            result = self.client.read_input_registers(4, 1, slave=0)
            if not result.isError():
                di_word = result.registers[0]
                di_data = decode_di8_word(di_word)
                print(f"✓ DI-8-Karte: Raw={di_word}")
                return di_data
        except Exception as e:
            print(f"⚠ Fehler DI-8-Karte: {e}")
        return None
    
    def read_system_diagnostics(self) -> Optional[SystemDiagnostics]:
        """Liest System-Diagnose"""
        try:
            result = self.client.read_holding_registers(12352, 32, slave=0)
            if result.isError():
                return None
            
            reg = result.registers
            return SystemDiagnostics(
                uptime_sec=self.helper.get_dint(reg, 0),
                error_count=self.helper.get_dint(reg, 4),
                cpu_load=self.helper.get_dint(reg, 3),
                cycle_min_us=self.helper.get_dint(reg, 7),
                cycle_max_us=self.helper.get_dint(reg, 8),
                cycle_avg_us=self.helper.get_dint(reg, 9)
            )
        except Exception as e:
            print(f"⚠ Fehler System-Diagnose: {e}")
            return None
    
    def read_sps_version(self) -> Optional[SPSVersion]:
        """Liest SPS Version"""
        try:
            result = self.client.read_holding_registers(12358, 8, slave=0)
            if result.isError():
                return None
            
            major = self.helper.get_dint(result.registers, 0) & 0xFF
            minor = self.helper.get_dint(result.registers, 1) & 0xFF
            patch = self.helper.get_dint(result.registers, 2) & 0xFF
            serial = self.helper.get_dint(result.registers, 3)
            
            return SPSVersion(
                major=major,
                minor=minor,
                patch=patch,
                serial=serial,
                version_string=f"v{major}.{minor}.{patch}"
            )
            
        except Exception as e:
            print(f"⚠ Fehler SPS-Version: {e}")
            return None
    
    def read_alarms(self) -> List[str]:
        """Liest Alarme"""
        try:
            result = self.client.read_holding_registers(12416, 32, slave=0)
            if result.isError():
                return []
            
            alarm_word = self.helper.get_dint(result.registers, 0)
            return decode_alarm_word(alarm_word)
        except Exception as e:
            print(f"⚠ Fehler Alarme: {e}")
            return []

def run_sync():
    """Hauptfunktion"""
    now = datetime.now()
    
    mqtt_reader = MQTTTemperature(
        CONFIG.MQTT_BROKER, CONFIG.MQTT_PORT, 
        CONFIG.MQTT_TOPIC, CONFIG.MQTT_TIMEOUT
    )
    mqtt_temp = mqtt_reader.read()
    
    client = ModbusTcpClient(CONFIG.SPS_IP, port=CONFIG.SPS_PORT, 
                             timeout=CONFIG.SPS_TIMEOUT)
    if not client.connect():
        print("✗ Keine Verbindung zur SPS")
        sys.exit(1)
    
    try:
        helper = ModbusHelper()
        
        print("=== Prüfe Pumpen-Overrides ===")
        
        result = client.read_holding_registers(CONFIG.ADDR_WW_PUMPE, 6, slave=0)
        if not result.isError():
            current_ww = helper.get_dint(result.registers, 0)
            current_hk = helper.get_dint(result.registers, 1)
            current_br = helper.get_dint(result.registers, 2)
            
            if current_ww != CONFIG.WW_PUMPE_OVERRIDE:
                helper.write_dint(client, CONFIG.ADDR_WW_PUMPE, 
                                 CONFIG.WW_PUMPE_OVERRIDE, "WW-Pumpe")
            else:
                print(f"✓ WW-Pumpe bereits {current_ww}")
            
            if current_hk != CONFIG.HK_PUMPE_OVERRIDE:
                helper.write_dint(client, CONFIG.ADDR_HK_PUMPE, 
                                 CONFIG.HK_PUMPE_OVERRIDE, "HK-Pumpe")
            else:
                print(f"✓ HK-Pumpe bereits {current_hk}")
            
            if current_br != CONFIG.BRUNNEN_OVERRIDE:
                helper.write_dint(client, CONFIG.ADDR_BRUNNEN, 
                                 CONFIG.BRUNNEN_OVERRIDE, "Brunnen")
            else:
                print(f"✓ Brunnen bereits {current_br}")
        
        reader = SPSReader(client)
        
        # ====================================================================
        # TEST: DO5 (LED) setzen
        # ====================================================================
        print("\n" + "=" * 80)
        print("TEST: Setze DO5 (%QX0.5) - LED-Test via FC15")
        print("=" * 80)
        if reader.test_digital_output_write():
            print("⏳ Warte 3 Sekunden... (LED sollte leuchten!)")
            time.sleep(3)
            
            # Optional: Zurücksetzen via FC15
            result_qb = client.read_holding_registers(512, 1, slave=0)
            if not result_qb.isError():
                current = result_qb.registers[0] & 0xFF
                
                # Coil-Array erstellen mit Bit 5 = False (nur 6 Bits!)
                coils = []
                for i in range(6):
                    if i == 5:
                        coils.append(False)  # DO5 ausschalten
                    else:
                        coils.append(bool(current & (1 << i)))
                
                client.write_coils(512, coils, slave=0)
                print(f"✓ DO5 zurückgesetzt via FC15")
        print("=" * 80 + "\n")
        # ====================================================================
        
        client.write_register(12288, now.hour, slave=0)
        
        reason_ww, reason_hk, reason_br = reader.read_reason_bytes()
        
        pump_runtime = reader.read_pump_runtime()
        
        # PHYSISCHE AUSGÄNGE LESEN
        coil_ww, coil_hk, coil_br = reader.read_physical_outputs()
        
        di8_data = reader.read_di8_card()
        
        if not reader.wait_for_data_ready():
            print("✗ Kein Data-Ready")
            return
        
        result = client.read_holding_registers(12320, 32, slave=0)
        if result.isError():
            print("✗ Modbus Fehler")
            return
        
        registers = result.registers
        sensors = reader.read_sensors(registers)
        sensors.mqtt_temp = mqtt_temp
        
        # Status mit physischen Ausgängen dekodieren
        status = decode_status_word(registers[14 * 2], coil_ww, coil_hk, coil_br,
                                    reason_ww, reason_hk, reason_br)
        system = reader.read_system_diagnostics()
        sps_version = reader.read_sps_version()
        alarms = reader.read_alarms()
        
        print("=" * 80)
        print(f"PYTHON: {VERSION['string']} | {VERSION['date']} {VERSION['time']}")
        
        if sps_version:
            print(f"SPS ST: {sps_version.version_string} | Serial: {sps_version.serial}")
        
        print("=" * 80)
        print(f"ZEIT: {now.strftime('%Y-%m-%d %H:%M:%S')} | "
              f"PHASE: {status.phase} | DATA: {'READY' if status.data_ready else 'WAIT'}")
        print("-" * 80)
        
        print("REASON BYTES & ACTUATOR-STATUS:")
        print(f"  WW: {status.reason_ww_text}")
        print(f"  HK: {status.reason_hk_text}")
        print(f"  BR: {status.reason_br_text}")
        print("-" * 80)
        
        print("TEMPERATUREN:")
        print(f"  VL: {sensors.temp_vl:6.2f}°C | AT: {sensors.temp_at:6.2f}°C | "
              f"IT: {sensors.temp_it:6.2f}°C")
        print(f"  KE: {sensors.temp_ke:6.2f}°C | WW: {sensors.temp_ww:6.2f}°C | "
              f"RU: {sensors.temp_ru:6.2f}°C")
        print(f"  SO: {sensors.temp_so:6.2f}°C")
        
        temp_diff = sensors.temp_ke - sensors.temp_ww
        print(f"  ΔT(Kessel-WW): {temp_diff:.2f}°C (Schwelle: 2.0°C)")
        
        if mqtt_temp is not None:
            print(f"  MQTT: {mqtt_temp}°C")
        
        if di8_data:
            print("-" * 80)
            print(f"DI: {format_di8_status(di8_data)}")
        
        # Grafische DO-Anzeige
        print("-" * 80)
        do_status = format_do_status(coil_ww, coil_hk, coil_br, registers[14 * 2])
        print(f"DO: {do_status}")
        
        print("-" * 80)
        print(f"PUMPEN (Physische Ausgänge):")
        print(f"  WW: {'AN ' if status.ww_pumpe else 'AUS'} | "
              f"HK: {'AN ' if status.hz_pumpe else 'AUS'} | "
              f"BR: {'AN ' if status.brunnen else 'AUS'}")
        
        if pump_runtime:
            print(f"  Runtime: WW={format_runtime(pump_runtime.ww_hours)} | "
                  f"HK={format_runtime(pump_runtime.hk_hours)} | "
                  f"BR={format_runtime(pump_runtime.br_hours)}")
        
        # WARNUNG bei Diskrepanz
        warnings = []
        if status.ww_pumpe != status.ww_pumpe_modbus:
            warnings.append(f"WW: Physisch={'AN' if status.ww_pumpe else 'AUS'}, "
                          f"Modbus={'AN' if status.ww_pumpe_modbus else 'AUS'}")
        if status.hz_pumpe != status.hz_pumpe_modbus:
            warnings.append(f"HK: Physisch={'AN' if status.hz_pumpe else 'AUS'}, "
                          f"Modbus={'AN' if status.hz_pumpe_modbus else 'AUS'}")
        if status.brunnen != status.brunnen_modbus:
            warnings.append(f"BR: Physisch={'AN' if status.brunnen else 'AUS'}, "
                          f"Modbus={'AN' if status.brunnen_modbus else 'AUS'}")
        
        if warnings:
            print("-" * 80)
            print("⚠️  MODBUS-DISKREPANZ (Modbus-Status != Physischer Ausgang):")
            for w in warnings:
                print(f"  • {w}")
            print("  → SPS-Code: Modbus-Mapping muss NACH Override erfolgen!")
        
        if system:
            print("-" * 80)
            print(f"SYSTEM: Uptime {format_uptime(system.uptime_sec)} | "
                  f"Fehler: {system.error_count} | CPU: {system.cpu_load}%")
        
        if alarms:
            print("-" * 80)
            print("⚠ ALARME:")
            for alarm in alarms[:5]:
                print(f"  • {alarm}")
        
        print("=" * 80)
        
        conn = pymysql.connect(**CONFIG.DB_CONFIG)
        try:
            with conn.cursor() as cur:
                sql = """INSERT INTO heizung 
                         (version, zeitstempel, sensor_gruppe, stunde, 
                          zaehler_kwh, zaehler_pumpe, zaehler_brunnen,
                          raw_vorlauf, raw_aussen, raw_innen, raw_kessel, 
                          temp_vorlauf, temp_aussen, temp_innen, temp_kessel, 
                          raw_warmwasser, temp_warmwasser, wert_oeltank, 
                          raw_ruecklauf, temp_ruecklauf, raw_solar, temp_solar, 
                          ky9a, status_word, di8_raw,
                          reason_ww, reason_hk, reason_br,
                          runtime_ww_h, runtime_hk_h, runtime_br_h,
                          cycles_ww, cycles_hk, cycles_br)
                         VALUES (%s,%s,%s,%s, %s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, 
                                 %s,%s,%s, %s,%s,%s,%s, %s,%s,%s, %s,%s,%s,
                                 %s,%s,%s, %s,%s,%s)"""
                
                # SPS-Version als DECIMAL(3,1) formatieren: 6.4.8 → 6.4
                sps_ver = float(f"{sps_version.major}.{sps_version.minor}") if sps_version else 0.0
                
                cur.execute(sql, (
                    sps_ver, now, status.phase, now.hour,
                    helper.get_max_word(registers, 0),
                    helper.get_max_word(registers, 1),
                    helper.get_max_word(registers, 2),
                    sensors.raw_vl, sensors.raw_at, sensors.raw_it, sensors.raw_ke,
                    sensors.temp_vl, sensors.temp_at, sensors.temp_it, sensors.temp_ke,
                    sensors.raw_ww, sensors.temp_ww, sensors.temp_ot,
                    sensors.raw_ru, sensors.temp_ru, sensors.raw_so, sensors.temp_so,
                    mqtt_temp, registers[14 * 2],
                    di8_data['raw_value'] if di8_data else None,
                    status.reason_ww, status.reason_hk, status.reason_br,
                    pump_runtime.ww_hours if pump_runtime else 0,
                    pump_runtime.hk_hours if pump_runtime else 0,
                    pump_runtime.br_hours if pump_runtime else 0,
                    pump_runtime.ww_cycles if pump_runtime else 0,
                    pump_runtime.hk_cycles if pump_runtime else 0,
                    pump_runtime.br_cycles if pump_runtime else 0
                ))
            
            conn.commit()
            print("✓ Daten in DB gespeichert.")
        finally:
            conn.close()
    
    except Exception as e:
        print(f"✗ Fehler: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ['--version', '-v']:
        print_version()
        sys.exit(0)
    
    run_sync()
