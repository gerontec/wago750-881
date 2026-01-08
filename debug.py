#!/usr/bin/env python3
# wagostatus.py v1.3.7 - Präzises OSCAT-Debugging
import sys
import datetime
from pymodbus.client import ModbusTcpClient

VERSION = '1.3.7'
SPS_IP = '192.168.178.2'
CONST_VL_SOLL_MIN = 50.0

def to_uint(val): return val if val >= 0 else val + 65536
def to_int(val): return val if val < 32768 else val - 65536

def main():
    client = ModbusTcpClient(SPS_IP, port=502, timeout=5)
    if not client.connect(): sys.exit(1)
    
    now = datetime.datetime.now().strftime("%H:%M:%S")
    
    try:
        reg = client.read_holding_registers(12320, 32, slave=0).registers
        sp  = client.read_holding_registers(12384, 16, slave=0).registers

        # 1. Messwerte
        status_word = reg[10]
        qb0 = to_uint(reg[31]) & 0xFF
        temp_vl = to_int(reg[14]) / 100.0
        temp_at = to_int(reg[27]) / 100.0
        frost   = to_int(sp[9]) / 100.0
        nacht   = bool(status_word & 0x08)
        
        # 2. Soll-Analyse laut PLC_PRG Logik
        # Logik: bHK_Reason := (temp_at < frost) OR (temp_vl < 50 AND NOT nacht)
        anforderung_frost = (temp_at < frost)
        anforderung_wärme = (temp_vl < CONST_VL_SOLL_MIN) and not nacht
        hk_soll_an = anforderung_frost or anforderung_wärme

        # 3. Ist-Zustand (Relais NC)
        # Bit 2 (0x04): 1 = Relais zieht an = Pumpe AUS
        hk_relais_an = bool(qb0 & 0x04)
        hk_ist_an = not hk_relais_an

        print(f"WAGO STATUS v{VERSION} | {now} | VL: {temp_vl}°C | AT: {temp_at}°C")
        print("-" * 50)
        
        # DEBUG Sektion
        print(f"DIAGNOSE HK-PUMPE (OSCAT ACTUATOR_PUMP):")
        print(f"  Soll-Zustand: {'[AN]' if hk_soll_an else '[AUS]'}")
        print(f"  Grund:        {'Frostschutz' if anforderung_frost else 'Wärmebedarf' if anforderung_wärme else 'Keiner'}")
        print(f"  Ist-Zustand:  {'[AN]' if hk_ist_an else '[AUS]'} (Relais: {'Aktiv' if hk_relais_an else 'Abgefallen'})")
        
        if hk_soll_an and not hk_ist_an:
            print(f"  STATUS:       SPERRE AKTIV (OSCAT Timer blockiert)")
            print(f"                -> Entweder MIN_OFFTIME (120s) noch nicht um")
            print(f"                -> Oder Vorlauf war kurzzeitig > 50°C")
        elif not hk_soll_an and hk_ist_an:
            print(f"  STATUS:       NACHLAUF AKTIV (OSCAT MIN_ONTIME 300s)")
        else:
            print(f"  STATUS:       OK (Soll == Ist)")

        # Statistik
        print(f"\nSTATISTIK:")
        print(f"  HK-Laufzeit:  {to_uint(reg[19])}s | Starts: {to_uint(reg[22])}")
        print(f"  WW-Laufzeit:  {to_uint(reg[18])}s | Starts: {to_uint(reg[21])}")

    finally:
        client.close()

if __name__ == "__main__":
    main()
