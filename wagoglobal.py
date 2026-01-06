#!/usr/bin/env python3
# wagostatus.py v1.5.1 - 1:1 Global Mapping Logic
import sys
import datetime
from pymodbus.client import ModbusTcpClient

VERSION = '1.5.1'
SPS_IP = '192.168.178.2'

def to_int(val): return val if val < 32768 else val - 65536
def to_uint(val): return val if val >= 0 else val + 65536

def main():
    client = ModbusTcpClient(SPS_IP, port=502, timeout=5)
    if not client.connect():
        print(f"✗ Verbindung zu {SPS_IP} fehlgeschlagen")
        sys.exit(1)
    
    try:
        # --- 1:1 REGISTER READS (Mapping laut deiner VAR_GLOBAL) ---
        # MW0-15: Basis-Zähler (12288)
        xNewVar7 = client.read_holding_registers(12288, 16, slave=0).registers
        # MW32-63: xMeasure (12320)
        xMeasure = client.read_holding_registers(12320, 32, slave=0).registers
        # MW96-111: xSetpoints (12384)
        xSetpoints = client.read_holding_registers(12384, 16, slave=0).registers
        # MW128-135: xSystem (12416)
        xSystem = client.read_holding_registers(12416, 8, slave=0).registers
        # MW144-151: xAlarms (12432)
        xAlarms = client.read_holding_registers(12432, 8, slave=0).registers
        # MW160-167: xStats (12448)
        xStats = client.read_holding_registers(12448, 8, slave=0).registers

        # --- VARIABLEN EXTRAKTION (Strikt nach Kommentarliste) ---
        uptime_sec = (xSystem[1] << 16) | xSystem[0]
        status_word = xMeasure[10] # MW42
        qb0_phys = xMeasure[31]    # MW63
        
        print("="*85)
        print(f"WAGO 750-881 STATUS | v{VERSION} | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"System Uptime: {uptime_sec // 3600}h {(uptime_sec % 3600) // 60}m {uptime_sec % 60}s")
        print("="*85)

        # 1. PHYSIKALISCHE KLEMMEN & SAMPLE-HOLD (MW32-MW40)
        print(f"▶ PHYSIKALISCHE KLEMMEN & S+H:")
        print(f"  S_Vorlauf: {xMeasure[0]:5d} | S_Aussen:  {xMeasure[1]:5d} | S_Innen:   {xMeasure[2]:5d}")
        print(f"  S_Kessel:  {xMeasure[3]:5d} | S_Warmw:   {xMeasure[4]:5d} | S_Solar:   {xMeasure[7]:5d}")
        print(f"  DI8-Chan:  0x{xMeasure[8]:02X}  | HourOfDay: {xMeasure[9]:d}")

        # 2. BERECHNETE TEMPERATUREN (MW43-MW46 & MW59-MW62)
        print(f"\n▶ TEMPERATUREN (REAL-Mapping):")
        print(f"  Vorlauf:  {to_int(xMeasure[14])/100.0:6.2f}°C | Kessel:   {to_int(xMeasure[12])/100.0:6.2f}°C")
        print(f"  Aussen:   {to_int(xMeasure[27])/100.0:6.2f}°C | Warmw:    {to_int(xMeasure[13])/100.0:6.2f}°C")
        print(f"  Ruecklauf:{to_int(xMeasure[29])/100.0:6.2f}°C | Solar:    {to_int(xMeasure[30])/100.0:6.2f}°C")
        print(f"  ΔT(K-W):  {to_int(xMeasure[11])/100.0:6.2f}°C")

        # 3. SETPOINTS & KONFIGURATION (MW96-MW111)
        print(f"\n▶ SETPOINTS & KONFIG (xSetpoints):")
        print(f"  Soll-VL:  {to_int(xSetpoints[0])/100.0:6.2f}°C | Soll-WW:  {to_int(xSetpoints[1])/100.0:6.2f}°C")
        print(f"  Hyst-VL:  {to_int(xSetpoints[2])/100.0:6.2f}°C | Hyst-WW:  {to_int(xSetpoints[3])/100.0:6.2f}°C")
        print(f"  FrostLim: {to_int(xSetpoints[9])/100.0:6.2f}°C | Nachlauf: {xSetpoints[11]:4d}s")
        print(f"  Absenk:   {xSetpoints[4]:02d}:00-{xSetpoints[5]:02d}:00 Uhr ({to_int(xSetpoints[6])/100.0}°C)")

        # 4. LOGIK-DIAGNOSE (MW42 & MW56-MW58)
        print(f"\n▶ LOGIK-ZUSTAND:")
        print(f"  bHK_Reason: 0x{xMeasure[25]:02X} (F:{bool(xMeasure[25]&1)} W:{bool(xMeasure[25]&2)} O:{bool(xMeasure[25]&4)})")
        print(f"  bWW_Reason: 0x{xMeasure[24]:02X} | bBR_Reason: 0x{xMeasure[26]:02X}")
        print(f"  HK-Override: {to_int(xSetpoints[14])} | WW-Override: {to_int(xSetpoints[13])}")
        
        # Status-Word aufschlüsseln
        sw = status_word
        print(f"  Status: 0x{sw:04X} [Nacht:{bool(sw&8)} Mux:{'A' if sw&16 else 'B'} Ready:{bool(sw&32)} Err:{bool(sw&64)}]")

        # 5. HARDWARE OUTPUTS & STATS (MW63 & MW50-MW55 & MW160-165)
        print(f"\n▶ HARDWARE & BETRIEB:")
        hk_on = not bool(qb0_phys & 0x04) # O2_UmwaelzHK1
        ww_on = not bool(qb0_phys & 0x02) # O1_WWPump
        br_on = bool(qb0_phys & 0x08)     # O3_Brunnen (Relais Schließer)
        
        print(f"  PUMPE HK:  {'[RUN]' if hk_on else '[OFF]'} | Starts: {xStats[3]:5d} | {xStats[0]:4d}h | Akt: {to_uint(xMeasure[19])}s")
        print(f"  PUMPE WW:  {'[RUN]' if ww_on else '[OFF]'} | Starts: {xStats[4]:5d} | {xStats[1]:4d}h | Akt: {to_uint(xMeasure[18])}s")
        print(f"  BRUNNEN:   {'[RUN]' if br_on else '[OFF]'} | Starts: {xStats[5]:5d} | {xStats[2]:4d}h | Akt: {to_uint(xMeasure[20])}s")

        # 6. SYSTEM & ALARME (MW128-135 & MW144-151)
        print(f"\n▶ SYSTEM:")
        print(f"  CPU-Load: {xSystem[3]:3d}% | Cycle Avg: {xSystem[6]:3d}ms (Min:{xSystem[4]} Max:{xSystem[5]})")
        if xAlarms[0] > 0:
            print(f"  ⚠ ALARME: 0x{xAlarms[0]:04X} -> VL:{bool(xAlarms[0]&1)} AT:{bool(xAlarms[0]&2)} KE:{bool(xAlarms[0]&4)} WW:{bool(xAlarms[0]&8)}")

        print("="*85)

    finally:
        client.close()

if __name__ == "__main__":
    main()
