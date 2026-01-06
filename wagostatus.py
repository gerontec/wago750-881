#!/usr/bin/env python3
# wagostatus.py - Zeigt physische I/O Ports UND alle globalen Variablen der WAGO 750-881
import sys
from pymodbus.client import ModbusTcpClient

VERSION = '1.1.0'
SPS_IP = '192.168.178.2'

# Modbus Register Adressen
ADDR_MEASURE = 12320    # xMeasure[1..32] - MW32-MW63
ADDR_SETPOINTS = 12384  # xSetpoints[1..16] - MW96-MW111
ADDR_SYSTEM = 12416     # xSystem[1..8] - MW128-MW135

def to_uint(val):
    """Konvertiert signed zu unsigned"""
    return val if val >= 0 else val + 65536

def to_int(val):
    """Konvertiert unsigned zu signed"""
    return val if val < 32768 else val - 65536

def calc_pt1000(raw):
    """Berechnet PT1000 Temperatur"""
    if not (4000 <= raw <= 25000):
        return None
    return round((float(raw) - 7134.0) / 25.0, 2)

def calc_boiler(raw):
    """Berechnet NTC Boiler Temperatur"""
    if not (4000 <= raw <= 45000):
        return None
    return round((40536.0 - float(raw)) / 303.1, 2)

def calc_solar(raw):
    """Berechnet NTC Solar Temperatur"""
    if not (4000 <= raw <= 40000):
        return None
    return round((float(raw) - 26402.0) / 60.0, 2)

def format_uptime(sec):
    """Formatiert Uptime"""
    d = sec // 86400
    h = (sec % 86400) // 3600
    m = (sec % 3600) // 60
    return f"{d}d {h:02d}h {m:02d}m"

def main():
    client = ModbusTcpClient(SPS_IP, port=502, timeout=5)
    if not client.connect():
        print("✗ Keine Verbindung zur SPS")
        sys.exit(1)
    
    try:
        # =====================================================================
        # 1. PHYSISCHE I/O LESEN
        # =====================================================================
        result = client.read_holding_registers(ADDR_MEASURE, 32, slave=0)
        if result.isError():
            print("✗ Modbus Fehler")
            return
        
        reg = result.registers
        
        # Analog Inputs (Raw-Werte) - PHYSISCH
        ai0 = to_uint(reg[0])  # xMeasure[1] - %IW0
        ai1 = to_uint(reg[1])  # xMeasure[2] - %IW1
        ai2 = to_uint(reg[2])  # xMeasure[3] - %IW2
        ai3 = to_uint(reg[3])  # xMeasure[4] - %IW3
        
        # Digital Input - PHYSISCH
        di8 = to_uint(reg[8])  # xMeasure[9] - %IW4 (DI8chan)
        
        # Status Word
        status = reg[10]       # xMeasure[11]
        mux_phase = 'A' if (status & 0x10) else 'B'
        data_ready = bool(status & 0x20)
        nacht = bool(status & 0x08)
        sensor_error = bool(status & 0x40)
        
        # Physical Output Byte - PHYSISCH
        qb0 = to_uint(reg[31]) & 0xFF  # xMeasure[32] - %QB0
        
        # Sample & Hold Werte (gesampelte Werte)
        s_vorlauf = to_uint(reg[0])   # xMeasure[1]
        s_aussen = to_uint(reg[1])    # xMeasure[2]
        s_innen = to_uint(reg[2])     # xMeasure[3]
        s_kessel = to_uint(reg[3])    # xMeasure[4]
        s_warmw = to_uint(reg[4])     # xMeasure[5]
        s_oeltank = to_uint(reg[5])   # xMeasure[6]
        s_ruecklauf = to_uint(reg[6]) # xMeasure[7]
        s_solar = to_uint(reg[7])     # xMeasure[8]
        
        # Berechnete Temperaturen
        temp_vl = calc_pt1000(s_vorlauf if mux_phase == 'A' else s_warmw)
        temp_at = calc_pt1000(s_aussen if mux_phase == 'A' else s_oeltank)
        temp_it = calc_pt1000(s_innen if mux_phase == 'A' else s_ruecklauf)
        temp_ke = calc_pt1000(s_kessel if mux_phase == 'A' else s_solar)
        temp_ww = calc_boiler(s_warmw)
        temp_so = calc_solar(s_solar)
        
        # SPS-berechnete Werte
        hour_of_day = to_int(reg[9])      # xMeasure[10]
        temp_diff_ww = to_int(reg[11]) / 100.0   # xMeasure[12]
        temp_ke_sps = to_int(reg[12]) / 100.0    # xMeasure[13]
        temp_ww_sps = to_int(reg[13]) / 100.0    # xMeasure[14]
        temp_vl_sps = to_int(reg[14]) / 100.0    # xMeasure[15]
        
        # Version
        version_word = to_uint(reg[15])
        major = (version_word >> 8) & 0xFF
        minor = version_word & 0xFF
        patch = to_int(reg[16])       # xMeasure[17]
        serial = to_int(reg[17])      # xMeasure[18]
        
        # Runtime & Cycles
        runtime_ww = to_uint(reg[18])  # xMeasure[19] in Sekunden
        runtime_hk = to_uint(reg[19])  # xMeasure[20]
        runtime_br = to_uint(reg[20])  # xMeasure[21]
        cycles_ww = to_uint(reg[21])   # xMeasure[22]
        cycles_hk = to_uint(reg[22])   # xMeasure[23]
        cycles_br = to_uint(reg[23])   # xMeasure[24]
        
        # Reason Bytes
        reason_ww = to_uint(reg[24]) & 0xFF  # xMeasure[25]
        reason_hk = to_uint(reg[25]) & 0xFF  # xMeasure[26]
        reason_br = to_uint(reg[26]) & 0xFF  # xMeasure[27]
        
        # Weitere Temperaturen
        temp_at_sps = to_int(reg[27]) / 100.0   # xMeasure[28]
        temp_it_sps = to_int(reg[28]) / 100.0   # xMeasure[29]
        temp_ru_sps = to_int(reg[29]) / 100.0   # xMeasure[30]
        temp_so_sps = to_int(reg[30]) / 100.0   # xMeasure[31]
        
        # =====================================================================
        # 2. SETPOINTS LESEN
        # =====================================================================
        setpoints_result = client.read_holding_registers(ADDR_SETPOINTS, 16, slave=0)
        if not setpoints_result.isError():
            sp = setpoints_result.registers
            nacht_start = to_int(sp[4])    # xSetpoints[5]
            nacht_end = to_int(sp[5])      # xSetpoints[6]
            frost_schwelle = to_int(sp[9]) / 100.0 if sp[9] != 0 else None  # xSetpoints[10]
            tank_temp = to_int(sp[12]) / 100.0 if sp[12] != 0 else None     # xSetpoints[13]
            ww_override = to_int(sp[13])   # xSetpoints[14]
            hk_override = to_int(sp[14])   # xSetpoints[15]
            br_override = to_int(sp[15])   # xSetpoints[16]
        else:
            nacht_start = nacht_end = frost_schwelle = tank_temp = None
            ww_override = hk_override = br_override = 0
        
        # =====================================================================
        # 3. SYSTEM-DIAGNOSE LESEN
        # =====================================================================
        sys_result = client.read_holding_registers(ADDR_SYSTEM, 8, slave=0)
        if not sys_result.isError():
            sys_reg = sys_result.registers
            uptime_low = sys_reg[0]
            uptime_high = sys_reg[1]
            uptime_sec = (uptime_high << 16) | uptime_low
            error_count = sys_reg[2]
            cpu_load = sys_reg[3]
        else:
            uptime_sec = error_count = cpu_load = 0
        
        # =====================================================================
        # AUSGABE
        # =====================================================================
        print("=" * 80)
        print(f"WAGO 750-881 VOLLSTÄNDIGER STATUS | SPS v{major}.{minor}.{patch}")
        print("=" * 80)
        
        # PHYSISCHE I/O (mit Markierung)
        print("\n▶ PHYSISCHE ANALOG INPUTS (%IW0-3) - Raw 0-32767:")
        print(f"  %IW0 (AI0): {ai0:5d}  [Phase {mux_phase}: {'Vorlauf' if mux_phase=='A' else 'Warmw':8s}] → {temp_vl:.2f}°C" if temp_vl else f"  %IW0 (AI0): {ai0:5d}  [Phase {mux_phase}]")
        print(f"  %IW1 (AI1): {ai1:5d}  [Phase {mux_phase}: {'Aussen' if mux_phase=='A' else 'Öltank':8s}] → {temp_at:.2f}°C" if temp_at else f"  %IW1 (AI1): {ai1:5d}  [Phase {mux_phase}]")
        print(f"  %IW2 (AI2): {ai2:5d}  [Phase {mux_phase}: {'Innen' if mux_phase=='A' else 'Rücklauf':8s}] → {temp_it:.2f}°C" if temp_it else f"  %IW2 (AI2): {ai2:5d}  [Phase {mux_phase}]")
        print(f"  %IW3 (AI3): {ai3:5d}  [Phase {mux_phase}: {'Kessel' if mux_phase=='A' else 'Solar':8s}] → {temp_ke:.2f}°C" if temp_ke else f"  %IW3 (AI3): {ai3:5d}  [Phase {mux_phase}]")
        
        print(f"\n▶ PHYSISCHER DIGITAL INPUT (%IW4):")
        print(f"  DI8chan: 0x{di8:04X} = {di8:016b}b")
        active_bits = [f"DI{i}" for i in range(16) if di8 & (1 << i)]
        print(f"  Aktive Bits: {', '.join(active_bits) if active_bits else 'keine'}")
        
        print(f"\n▶ PHYSISCHE DIGITAL OUTPUTS (%QB0):")
        print(f"  QB0: 0x{qb0:02X} = {qb0:08b}b")
        print(f"    Bit0: {'1' if qb0 & 0x01 else '0'} - Output_0 (Mux)")
        print(f"    Bit1: {'1' if qb0 & 0x02 else '0'} - O1_WWPump {'[AUS]' if qb0 & 0x02 else '[AN]'} (NC)")
        print(f"    Bit2: {'1' if qb0 & 0x04 else '0'} - O2_UmwaelzHK1 {'[AUS]' if qb0 & 0x04 else '[AN]'} (NC)")
        print(f"    Bit3: {'1' if qb0 & 0x08 else '0'} - O3_Brunnen {'[AN]' if qb0 & 0x08 else '[AUS]'} (NO)")
        print(f"    Bit4: {'1' if qb0 & 0x10 else '0'} - (Reserve)")
        print(f"    Bit5: {'1' if qb0 & 0x20 else '0'} - O5")
        print(f"    Bit6: {'1' if qb0 & 0x40 else '0'} - (Reserve)")
        print(f"    Bit7: {'1' if qb0 & 0x80 else '0'} - (Reserve)")
        
        # SAMPLE & HOLD WERTE
        print(f"\n• SAMPLE & HOLD (Multiplexed):")
        print(f"  S_Vorlauf:   {s_vorlauf:5d}  S_Warmw:    {s_warmw:5d}")
        print(f"  S_Aussen:    {s_aussen:5d}  S_Oeltank:  {s_oeltank:5d}")
        print(f"  S_Innen:     {s_innen:5d}  S_Ruecklauf:{s_ruecklauf:5d}")
        print(f"  S_Kessel:    {s_kessel:5d}  S_Solar:    {s_solar:5d}")
        
        # BERECHNETE TEMPERATUREN
        print(f"\n• BERECHNETE TEMPERATUREN:")
        print(f"  Vorlauf:  {temp_vl_sps:6.2f}°C  |  Aussen:   {temp_at_sps:6.2f}°C")
        print(f"  Kessel:   {temp_ke_sps:6.2f}°C  |  Innen:    {temp_it_sps:6.2f}°C")
        print(f"  Warmw:    {temp_ww_sps:6.2f}°C  |  Rücklauf: {temp_ru_sps:6.2f}°C")
        print(f"  Solar:    {temp_so_sps:6.2f}°C  |  ΔT(KE-WW):{temp_diff_ww:6.2f}°C")
        if tank_temp:
            print(f"  R290 Tank:{tank_temp:6.2f}°C")
        
        # STEUERUNGSZUSTAND
        print(f"\n• STEUERUNG:")
        print(f"  Phase:        {mux_phase}")
        print(f"  Data Ready:   {'✓' if data_ready else '✗'}")
        print(f"  Nachtabsenkung: {'AKTIV' if nacht else 'INAKTIV'}", end='')
        if nacht_start is not None and nacht_end is not None:
            if 0 <= nacht_start <= 23 and 0 <= nacht_end <= 23:
                print(f" ({nacht_start:02d}:00-{nacht_end:02d}:00)")
            else:
                print(" (nicht konfiguriert)")
        else:
            print()
        print(f"  Sensor Error: {'✗ FEHLER' if sensor_error else '✓'}")
        print(f"  Stunde:       {hour_of_day}")
        if frost_schwelle:
            print(f"  Frostschutz:  < {frost_schwelle:.1f}°C")
        
        # PUMPEN-STATUS
        print(f"\n• PUMPEN:")
        ww_on = not (qb0 & 0x02)  # Invertiert
        hk_on = not (qb0 & 0x04)  # Invertiert
        br_on = bool(qb0 & 0x08)  # Normal
        
        print(f"  WW: {'AN ' if ww_on else 'AUS'} | Reason: 0x{reason_ww:02X}", end='')
        if ww_override != 0:
            print(f" | Override: {'ON' if ww_override > 0 else 'OFF'}")
        else:
            print(" | Auto")
        
        print(f"  HK: {'AN ' if hk_on else 'AUS'} | Reason: 0x{reason_hk:02X}", end='')
        if hk_override != 0:
            print(f" | Override: {'ON' if hk_override > 0 else 'OFF'}")
        else:
            print(" | Auto")
        
        print(f"  BR: {'AN ' if br_on else 'AUS'} | Reason: 0x{reason_br:02X}", end='')
        if br_override != 0:
            print(f" | Override: {'ON' if br_override > 0 else 'OFF'}")
        else:
            print(" | Auto")
        
        # BETRIEBSSTUNDEN
        print(f"\n• BETRIEBSSTUNDEN:")
        print(f"  WW: {format_uptime(runtime_ww)} ({cycles_ww} Starts)")
        print(f"  HK: {format_uptime(runtime_hk)} ({cycles_hk} Starts)")
        print(f"  BR: {format_uptime(runtime_br)} ({cycles_br} Starts)")
        
        # SYSTEM
        print(f"\n• SYSTEM:")
        print(f"  Uptime:  {format_uptime(uptime_sec)}")
        print(f"  Fehler:  {error_count}")
        print(f"  CPU:     {cpu_load}%")
        print(f"  Serial:  {serial}")
        
        print("=" * 80)
        
    except Exception as e:
        print(f"✗ Fehler: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()

if __name__ == "__main__":
    main()
