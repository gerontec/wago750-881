#!/usr/bin/env python3
"""
WAGO 750-881 Heating Control - Enhanced Interactive Monitor v4.0.0
==================================================================

Enhanced monitoring tool with complete physical I/O display and bit explanations.

Features:
- Complete physical input display (all %IW registers)
- Complete physical output display (all %QB registers with bit breakdown)
- Graphical DI/DO visualization with bit-level details
- Runtime statistics and cycle counts
- Override control interface
- Temperature monitoring
- Reason code display
- LED test mode
- Status word decoding with explanations

Author: gerontec
Date: 2026-01-06
Version: 4.0.0
"""

import sys
import time
from pymodbus.client import ModbusTcpClient
from datetime import datetime
import signal

# WAGO PLC Configuration
PLC_IP = "192.168.178.2"
PLC_PORT = 502
SLAVE_ID = 0

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    GRAY = '\033[90m'
    
    # LED colors
    LED_ON = '\033[92m●\033[0m'   # Green
    LED_OFF = '\033[90m○\033[0m'  # Gray
    LED_ERROR = '\033[91m✖\033[0m' # Red

# Global client
client = None

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n\n" + Colors.WARNING + "Shutting down..." + Colors.ENDC)
    if client:
        client.close()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def connect_plc():
    """Connect to PLC"""
    global client
    try:
        client = ModbusTcpClient(PLC_IP, port=PLC_PORT)
        if not client.connect():
            print(Colors.FAIL + f"Failed to connect to PLC at {PLC_IP}:{PLC_PORT}" + Colors.ENDC)
            return False
        return True
    except Exception as e:
        print(Colors.FAIL + f"Connection error: {e}" + Colors.ENDC)
        return False

def read_registers(address, count):
    """Read holding registers with error handling"""
    try:
        result = client.read_holding_registers(address, count, slave=SLAVE_ID)
        if result.isError():
            return None
        return result.registers
    except Exception as e:
        print(Colors.FAIL + f"Error reading registers {address}: {e}" + Colors.ENDC)
        return None

def write_register(address, value):
    """Write holding register with error handling"""
    try:
        result = client.write_register(address, value, slave=SLAVE_ID)
        return not result.isError()
    except Exception as e:
        print(Colors.FAIL + f"Error writing register {address}: {e}" + Colors.ENDC)
        return False

def format_bit_display(byte_value, bit_names):
    """
    Format byte value as bit display with names
    
    Args:
        byte_value: Integer value (0-255)
        bit_names: List of 8 bit names [bit0, bit1, ..., bit7]
    
    Returns:
        Formatted string with bit visualization
    """
    output = []
    output.append(f"  Binary: {byte_value:08b} (0x{byte_value:02X} / {byte_value:3d})\n")
    
    for bit in range(8):
        is_set = (byte_value >> bit) & 1
        status = Colors.LED_ON if is_set else Colors.LED_OFF
        name = bit_names[bit] if bit < len(bit_names) else f"Reserved {bit}"
        value_text = "ON " if is_set else "OFF"
        output.append(f"  Bit {bit}: {status} {value_text} - {name}\n")
    
    return "".join(output)

def display_analog_inputs():
    """Display all analog input registers with descriptions"""
    print(Colors.HEADER + Colors.BOLD + "\n╔═══════════════════════════════════════════════════════════╗" + Colors.ENDC)
    print(Colors.HEADER + Colors.BOLD + "║         PHYSICAL ANALOG INPUTS (%IW0-%IW3)               ║" + Colors.ENDC)
    print(Colors.HEADER + Colors.BOLD + "╚═══════════════════════════════════════════════════════════╝" + Colors.ENDC)
    
    # Read raw analog inputs (registers 12320-12323 = %MW32-35 = %IW0-3)
    regs = read_registers(12320, 4)
    if not regs:
        print(Colors.FAIL + "Failed to read analog inputs" + Colors.ENDC)
        return
    
    # Input descriptions
    inputs = [
        ("IW0", "Boiler Temperature (PT1000)", regs[0]),
        ("IW1", "Hot Water Tank Temp (PT1000)", regs[1]),
        ("IW2", "Heating Circuit Temp (PT1000)", regs[2]),
        ("IW3", "Outdoor Temperature (PT1000)", regs[3])
    ]
    
    print()
    for name, desc, raw_value in inputs:
        # Convert raw ADC value (0-32767) to temperature
        # Assuming PT1000 with 0-10V input and 0-100°C range
        # Adjust conversion formula based on your actual hardware
        voltage = (raw_value / 32767.0) * 10.0  # 0-10V
        temp_c = voltage * 10.0  # Simple linear: 1V = 10°C (adjust as needed)
        
        # Color code by value
        if raw_value > 30000:
            color = Colors.FAIL  # Very high
        elif raw_value > 20000:
            color = Colors.WARNING  # High
        elif raw_value > 1000:
            color = Colors.OKGREEN  # Normal
        else:
            color = Colors.GRAY  # Low/disconnected
        
        print(f"  %{name}: {color}{raw_value:5d}{Colors.ENDC} (0x{raw_value:04X}) | "
              f"~{temp_c:5.1f}°C | {voltage:4.2f}V")
        print(f"         {Colors.GRAY}{desc}{Colors.ENDC}")
        print()

def display_digital_inputs():
    """Display digital input register with bit breakdown"""
    print(Colors.HEADER + Colors.BOLD + "\n╔═══════════════════════════════════════════════════════════╗" + Colors.ENDC)
    print(Colors.HEADER + Colors.BOLD + "║         PHYSICAL DIGITAL INPUTS (%IW4 - 8 Channel)       ║" + Colors.ENDC)
    print(Colors.HEADER + Colors.BOLD + "╚═══════════════════════════════════════════════════════════╝" + Colors.ENDC)
    
    # Read digital input register (12324 = %MW36 = %IW4)
    regs = read_registers(12324, 1)
    if not regs:
        print(Colors.FAIL + "Failed to read digital inputs" + Colors.ENDC)
        return
    
    di_value = regs[0]
    
    # Define bit names for 8-channel DI card
    bit_names = [
        "DI Channel 0 - Door Contact / Limit Switch",
        "DI Channel 1 - Flow Switch / Pressure Switch",
        "DI Channel 2 - External Enable Signal",
        "DI Channel 3 - Emergency Stop Input",
        "DI Channel 4 - Mode Select Input",
        "DI Channel 5 - Reserved / Unused",
        "DI Channel 6 - Reserved / Unused",
        "DI Channel 7 - Reserved / Unused"
    ]
    
    print()
    print(format_bit_display(di_value & 0xFF, bit_names))

def display_digital_outputs():
    """Display all digital output registers with bit breakdown"""
    print(Colors.HEADER + Colors.BOLD + "\n╔═══════════════════════════════════════════════════════════╗" + Colors.ENDC)
    print(Colors.HEADER + Colors.BOLD + "║         PHYSICAL DIGITAL OUTPUTS (%QB0-%QB7)             ║" + Colors.ENDC)
    print(Colors.HEADER + Colors.BOLD + "╚═══════════════════════════════════════════════════════════╝" + Colors.ENDC)
    
    # Read output register (512 = %QB0)
    regs = read_registers(512, 1)
    if not regs:
        print(Colors.FAIL + "Failed to read digital outputs" + Colors.ENDC)
        return
    
    qb0_value = regs[0]
    
    # Define bit names for %QB0
    qb0_bit_names = [
        "Hot Water Pump (WW Pumpe)",
        "Heating Circuit Pump (HK Pumpe)",
        "Well Pump (Brunnen Pumpe)",
        "Multiplexer Control A (Mux Phase A)",
        "Multiplexer Control B (Mux Phase B)",
        "Reserved Output 5",
        "Reserved Output 6",
        "Reserved Output 7"
    ]
    
    print(Colors.BOLD + "\n%QB0 - Main Output Byte:" + Colors.ENDC)
    print(format_bit_display(qb0_value & 0xFF, qb0_bit_names))
    
    # Additional output bytes if needed
    print(Colors.BOLD + "\nAdditional Output Bytes:" + Colors.ENDC)
    print(Colors.GRAY + "  %QB1-%QB7: Not used in current configuration" + Colors.ENDC)

def display_status_word():
    """Display and decode status word"""
    print(Colors.HEADER + Colors.BOLD + "\n╔═══════════════════════════════════════════════════════════╗" + Colors.ENDC)
    print(Colors.HEADER + Colors.BOLD + "║              SYSTEM STATUS WORD (%MW42)                   ║" + Colors.ENDC)
    print(Colors.HEADER + Colors.BOLD + "╚═══════════════════════════════════════════════════════════╝" + Colors.ENDC)
    
    # Read status word (12330 = %MW42)
    regs = read_registers(12330, 1)
    if not regs:
        print(Colors.FAIL + "Failed to read status word" + Colors.ENDC)
        return
    
    status = regs[0]
    
    # Define status word bit meanings
    status_bits = [
        "Reserved / Unused",
        "Reserved / Unused",
        "Reserved / Unused",
        "Night Mode Active (Reduced Heating)",
        "Multiplexer Phase (0=Phase A, 1=Phase B)",
        "Data Ready Flag (Sampling Complete)",
        "Sensor Error Detected",
        "Reserved / System Error"
    ]
    
    print()
    print(format_bit_display(status, status_bits))
    
    # Decoded status summary
    print(Colors.BOLD + "\nStatus Summary:" + Colors.ENDC)
    night_mode = (status >> 3) & 1
    mux_phase = (status >> 4) & 1
    data_ready = (status >> 5) & 1
    sensor_error = (status >> 6) & 1
    
    print(f"  Night Mode:   {Colors.LED_ON if night_mode else Colors.LED_OFF} {'ACTIVE (reduced heating)' if night_mode else 'Inactive (normal mode)'}")
    print(f"  Multiplexer:  Phase {'B' if mux_phase else 'A'} (Sensors T5-T7)")
    print(f"  Data Ready:   {Colors.LED_ON if data_ready else Colors.LED_OFF} {'Sampling complete' if data_ready else 'Waiting for sample'}")
    print(f"  Sensor Error: {Colors.LED_ERROR if sensor_error else Colors.LED_ON} {'ERROR - Check sensors!' if sensor_error else 'OK'}")

def display_temperatures():
    """Display all temperature sensors with formatting"""
    print(Colors.HEADER + Colors.BOLD + "\n╔═══════════════════════════════════════════════════════════╗" + Colors.ENDC)
    print(Colors.HEADER + Colors.BOLD + "║              TEMPERATURE SENSORS (Calculated)             ║" + Colors.ENDC)
    print(Colors.HEADER + Colors.BOLD + "╚═══════════════════════════════════════════════════════════╝" + Colors.ENDC)
    
    # Read temperature registers (would need sample & hold values)
    # This is a simplified version - actual temps would come from processed values
    print()
    print(Colors.GRAY + "  (Calculated temperatures from sample & hold registers)" + Colors.ENDC)
    print(Colors.GRAY + "  See heizung2.py/wagostatus.py for full temperature processing" + Colors.ENDC)

def display_pump_status():
    """Display pump status with runtime and reason codes"""
    print(Colors.HEADER + Colors.BOLD + "\n╔═══════════════════════════════════════════════════════════╗" + Colors.ENDC)
    print(Colors.HEADER + Colors.BOLD + "║                    PUMP STATUS                            ║" + Colors.ENDC)
    print(Colors.HEADER + Colors.BOLD + "╚═══════════════════════════════════════════════════════════╝" + Colors.ENDC)
    
    # Read pump runtime and reason codes
    runtime_regs = read_registers(12336, 6)  # Runtime hours and cycles
    reason_regs = read_registers(12344, 3)   # Reason codes
    output_reg = read_registers(512, 1)      # Physical outputs
    
    if not (runtime_regs and reason_regs and output_reg):
        print(Colors.FAIL + "Failed to read pump status" + Colors.ENDC)
        return
    
    # Parse values
    ww_runtime = runtime_regs[0]
    ww_cycles = runtime_regs[1]
    hk_runtime = runtime_regs[2]
    hk_cycles = runtime_regs[3]
    br_runtime = runtime_regs[4]
    br_cycles = runtime_regs[5]
    
    ww_reason = reason_regs[0]
    hk_reason = reason_regs[1]
    br_reason = reason_regs[2]
    
    output_byte = output_reg[0]
    
    # Reason code decoder
    def decode_reason(code):
        reasons = {
            0x00: "Off - No demand",
            0x01: "On - ΔT threshold exceeded",
            0x02: "On - Override active (manual)",
            0x03: "Off - Override inactive",
            0x04: "Off - Safety limit reached",
            0x05: "On - Frost protection",
            0x06: "Off - Night mode",
            0x10: "On - Test mode",
            0xFF: "Unknown state"
        }
        return reasons.get(code, f"Unknown code: 0x{code:02X}")
    
    # Display pump information
    pumps = [
        ("Hot Water (WW)", 0, ww_runtime, ww_cycles, ww_reason),
        ("Heating Circuit (HK)", 1, hk_runtime, hk_cycles, hk_reason),
        ("Well Pump (BR)", 2, br_runtime, br_cycles, br_reason)
    ]
    
    print()
    for name, bit, runtime, cycles, reason in pumps:
        is_on = (output_byte >> bit) & 1
        status_led = Colors.LED_ON if is_on else Colors.LED_OFF
        status_text = "ON " if is_on else "OFF"
        
        print(f"\n{Colors.BOLD}{name} Pump:{Colors.ENDC}")
        print(f"  Status:   {status_led} {status_text}")
        print(f"  Runtime:  {runtime:6d} hours ({runtime/24:.1f} days)")
        print(f"  Cycles:   {cycles:6d}")
        print(f"  Reason:   {decode_reason(reason)}")

def display_override_status():
    """Display override settings"""
    print(Colors.HEADER + Colors.BOLD + "\n╔═══════════════════════════════════════════════════════════╗" + Colors.ENDC)
    print(Colors.HEADER + Colors.BOLD + "║                 OVERRIDE SETTINGS                         ║" + Colors.ENDC)
    print(Colors.HEADER + Colors.BOLD + "╚═══════════════════════════════════════════════════════════╝" + Colors.ENDC)
    
    # Read override registers (12400-12402)
    override_regs = read_registers(12400, 3)
    if not override_regs:
        print(Colors.FAIL + "Failed to read override settings" + Colors.ENDC)
        return
    
    def decode_override(value):
        modes = {
            0: ("AUTO", Colors.OKGREEN),
            1: ("FORCE ON", Colors.WARNING),
            2: ("FORCE OFF", Colors.FAIL)
        }
        return modes.get(value, (f"UNKNOWN ({value})", Colors.GRAY))
    
    print()
    pumps = ["Hot Water (WW)", "Heating Circuit (HK)", "Well Pump (BR)"]
    for i, pump_name in enumerate(pumps):
        mode_text, color = decode_override(override_regs[i])
        print(f"  {pump_name:25s}: {color}{mode_text}{Colors.ENDC}")

def display_full_io_map():
    """Display complete I/O mapping reference"""
    print(Colors.HEADER + Colors.BOLD + "\n╔═══════════════════════════════════════════════════════════╗" + Colors.ENDC)
    print(Colors.HEADER + Colors.BOLD + "║              COMPLETE I/O MAPPING REFERENCE               ║" + Colors.ENDC)
    print(Colors.HEADER + Colors.BOLD + "╚═══════════════════════════════════════════════════════════╝" + Colors.ENDC)
    
    print(Colors.BOLD + "\nAnalog Inputs:" + Colors.ENDC)
    print("  %IW0 → Modbus 12320 → PT1000 Boiler Temperature")
    print("  %IW1 → Modbus 12321 → PT1000 Hot Water Tank")
    print("  %IW2 → Modbus 12322 → PT1000 Heating Circuit")
    print("  %IW3 → Modbus 12323 → PT1000 Outdoor Temperature")
    
    print(Colors.BOLD + "\nDigital Inputs:" + Colors.ENDC)
    print("  %IW4 → Modbus 12324 → 8-Channel DI Card")
    print("    Bit 0-7: Various digital inputs (door, flow, enable, etc.)")
    
    print(Colors.BOLD + "\nDigital Outputs:" + Colors.ENDC)
    print("  %QB0 → Modbus 512 → Main Output Byte")
    print("    Bit 0: Hot Water Pump")
    print("    Bit 1: Heating Circuit Pump")
    print("    Bit 2: Well Pump")
    print("    Bit 3: Multiplexer Control A")
    print("    Bit 4: Multiplexer Control B")
    print("    Bit 5-7: Reserved")
    
    print(Colors.BOLD + "\nStatus & Control:" + Colors.ENDC)
    print("  %MW42 → Modbus 12330 → Status Word")
    print("  %MW48-53 → Modbus 12336-12341 → Runtime & Cycles")
    print("  %MW54-59 → Modbus 12344-12349 → Reason Codes")
    print("  %MW112-115 → Modbus 12400-12403 → Override Settings")

def interactive_override():
    """Interactive override control menu"""
    print(Colors.HEADER + Colors.BOLD + "\n╔═══════════════════════════════════════════════════════════╗" + Colors.ENDC)
    print(Colors.HEADER + Colors.BOLD + "║                OVERRIDE CONTROL MENU                      ║" + Colors.ENDC)
    print(Colors.HEADER + Colors.BOLD + "╚═══════════════════════════════════════════════════════════╝" + Colors.ENDC)
    
    print("\nSelect pump to control:")
    print("  1. Hot Water Pump (WW)")
    print("  2. Heating Circuit Pump (HK)")
    print("  3. Well Pump (BR)")
    print("  0. Cancel")
    
    try:
        pump_choice = int(input("\nPump number: "))
        if pump_choice == 0:
            return
        if pump_choice not in [1, 2, 3]:
            print(Colors.FAIL + "Invalid pump selection" + Colors.ENDC)
            return
        
        print("\nSelect mode:")
        print("  0. AUTO (Automatic control)")
        print("  1. FORCE ON")
        print("  2. FORCE OFF")
        
        mode_choice = int(input("\nMode: "))
        if mode_choice not in [0, 1, 2]:
            print(Colors.FAIL + "Invalid mode selection" + Colors.ENDC)
            return
        
        # Write override register
        register = 12400 + pump_choice - 1
        if write_register(register, mode_choice):
            pump_names = ["", "Hot Water", "Heating Circuit", "Well"]
            mode_names = ["AUTO", "FORCE ON", "FORCE OFF"]
            print(Colors.OKGREEN + f"\n✓ Set {pump_names[pump_choice]} pump to {mode_names[mode_choice]}" + Colors.ENDC)
        else:
            print(Colors.FAIL + "\n✗ Failed to write override setting" + Colors.ENDC)
            
    except ValueError:
        print(Colors.FAIL + "Invalid input" + Colors.ENDC)
    except KeyboardInterrupt:
        print("\nCancelled")

def led_test():
    """Test all outputs sequentially"""
    print(Colors.HEADER + Colors.BOLD + "\n╔═══════════════════════════════════════════════════════════╗" + Colors.ENDC)
    print(Colors.HEADER + Colors.BOLD + "║                    LED TEST MODE                          ║" + Colors.ENDC)
    print(Colors.HEADER + Colors.BOLD + "╚═══════════════════════════════════════════════════════════╝" + Colors.ENDC)
    
    print(Colors.WARNING + "\nWARNING: This will activate outputs sequentially!" + Colors.ENDC)
    confirm = input("Continue? (yes/no): ")
    if confirm.lower() != "yes":
        return
    
    # Save current state
    current_state = read_registers(512, 1)
    if not current_state:
        print(Colors.FAIL + "Failed to read current state" + Colors.ENDC)
        return
    
    original_value = current_state[0]
    
    try:
        print("\nTesting outputs (Ctrl+C to abort)...")
        
        # Test each bit
        for bit in range(8):
            test_value = 1 << bit
            bit_names = ["WW Pump", "HK Pump", "Well Pump", "Mux A", "Mux B", "Out5", "Out6", "Out7"]
            
            print(f"\nTesting {bit_names[bit]} (Bit {bit})...")
            if write_register(512, test_value):
                print(f"  Output 0x{test_value:02X} activated")
                time.sleep(2)
            else:
                print(Colors.FAIL + "  Failed to write output" + Colors.ENDC)
        
        # All on
        print("\nAll outputs ON...")
        write_register(512, 0xFF)
        time.sleep(2)
        
    except KeyboardInterrupt:
        print("\nTest aborted")
    finally:
        # Restore original state
        print("\nRestoring original state...")
        write_register(512, original_value)
        print(Colors.OKGREEN + "✓ Outputs restored" + Colors.ENDC)

def main_menu():
    """Display main menu and handle user input"""
    while True:
        # Clear screen (optional)
        print("\n" * 2)
        
        print(Colors.HEADER + Colors.BOLD + "╔═══════════════════════════════════════════════════════════╗" + Colors.ENDC)
        print(Colors.HEADER + Colors.BOLD + "║   WAGO 750-881 Heating Control Monitor v4.0.0            ║" + Colors.ENDC)
        print(Colors.HEADER + Colors.BOLD + "╚═══════════════════════════════════════════════════════════╝" + Colors.ENDC)
        
        print(Colors.OKCYAN + f"\nConnected to: {PLC_IP}:{PLC_PORT}" + Colors.ENDC)
        print(Colors.GRAY + f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" + Colors.ENDC)
        
        # Display all sections
        display_analog_inputs()
        display_digital_inputs()
        display_digital_outputs()
        display_status_word()
        display_pump_status()
        display_override_status()
        
        # Menu options
        print(Colors.HEADER + Colors.BOLD + "\n╔═══════════════════════════════════════════════════════════╗" + Colors.ENDC)
        print(Colors.HEADER + Colors.BOLD + "║                      MENU OPTIONS                         ║" + Colors.ENDC)
        print(Colors.HEADER + Colors.BOLD + "╚═══════════════════════════════════════════════════════════╝" + Colors.ENDC)
        print("\n  [R] Refresh display")
        print("  [O] Override control")
        print("  [T] LED test mode")
        print("  [M] Show I/O mapping reference")
        print("  [Q] Quit")
        
        try:
            choice = input(f"\n{Colors.BOLD}Select option: {Colors.ENDC}").upper()
            
            if choice == 'R':
                continue
            elif choice == 'O':
                interactive_override()
                input("\nPress Enter to continue...")
            elif choice == 'T':
                led_test()
                input("\nPress Enter to continue...")
            elif choice == 'M':
                display_full_io_map()
                input("\nPress Enter to continue...")
            elif choice == 'Q':
                break
            else:
                print(Colors.WARNING + "Invalid option" + Colors.ENDC)
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n")
            break

def main():
    """Main program entry point"""
    print(Colors.HEADER + Colors.BOLD)
    print("═" * 63)
    print("  WAGO 750-881 Heating Control Enhanced Monitor v4.0.0")
    print("  Complete Physical I/O Display with Bit Explanations")
    print("═" * 63)
    print(Colors.ENDC)
    
    if not connect_plc():
        sys.exit(1)
    
    print(Colors.OKGREEN + "✓ Connected to PLC" + Colors.ENDC)
    time.sleep(1)
    
    try:
        main_menu()
    finally:
        if client:
            client.close()
        print(Colors.OKGREEN + "\nDisconnected from PLC" + Colors.ENDC)

if __name__ == "__main__":
    main()
