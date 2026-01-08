# WAGO 750-881 Heating Control System

Professional heating control system for WAGO 750-881 PLC with Python monitoring, MySQL data logging, and heat pump integration.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![PLC](https://img.shields.io/badge/PLC-WAGO%20750--881-orange.svg)](https://www.wago.com)
[![Python](https://img.shields.io/badge/python-3.x-blue.svg)](https://www.python.org)

## Overview

Multi-source heating control system featuring:
- **Oil Heating Control**: WAGO 750-881 PLC with 3 pumps (hot water, heating circuit, well pump)
- **R290 Heat Pump Integration**: Powerworld R290 air-water heat pump via Modbus RTU
- **Cross-System Optimization**: Automatic load sharing between oil boiler and heat pump
- **Temperature-based Control**: ΔT logic, override functionality, comprehensive monitoring

### Hardware Configuration

#### WAGO 750-881 PLC
* **PLC**: WAGO 750-881 (Modbus TCP Master)
* **Sensors**: 
  - 5× PT1000 temperature sensors
  - 2× NTC temperature sensors
  - 1× Oil tank level sensor
* **Outputs**: 3× Pump relays + Multiplexer control
* **Inputs**: 8-channel digital input card

#### Powerworld R290 Heat Pump
* **Connection**: Modbus RTU (RS485)
* **Port**: /dev/ttyUSB3 @ 9600 baud
* **Integration**: Tank temperature shared with WAGO PLC
* **Data Logging**: MySQL + MQTT publishing

## System Components

### PLC Program (v6.5.2)

**Main Program Files:**
* `heizung.st` - Main control logic (Structured Text)
* `globalvar.st` - Global variable declarations

**Key Features:**
* **ΔT-based control**: Pumps activate when temperature difference ≥ 2°C
* **OSCAT Integration**: Uses ACTUATOR_PUMP function blocks for reliable pump control
* **Override functionality**: Manual pump control via Modbus registers
* **Runtime tracking**: Non-retained runtime counters (survives PLC restarts)
* **Reason code tracking**: Detailed logging why pumps are on/off
* **Night mode**: Reduced heating during configurable night hours
* **Frost protection**: Automatic activation below threshold temperature
* **Fail-safe design**: Inverted relay logic for critical pumps

**Control Logic:**
- Hot water pump: Boiler > HW tank + 2°C (runs 24/7, ignores night mode)
- Heating pump: Boiler > HC flow + 2°C (respects night mode, frost override)
- Well pump: Always ON (continuous circulation)
- All pumps respect override settings and safety limits

### Python Scripts

#### heizung3.py (v4.1.0) - Enhanced Interactive Monitor

Complete physical I/O monitoring with bit-level explanations.

**Features:**
* **Complete I/O Display**:
  - All analog inputs (%IW0-%IW3) with RAW, voltage, temperature
  - Digital inputs (%IW4) with 8-bit breakdown
  - Digital outputs (%QB0) with inverted relay logic explained
* **Graphical Status Display**: Visual DI/DO with color-coded LEDs
* **Runtime Statistics**: Per-pump runtime hours and cycle counts
* **Override Control**: Interactive pump override management
* **LED Test Mode**: Test all outputs sequentially
* **Status Word Decoding**: Complete bit explanation
* **Reason Code Display**: Shows why each pump is active/inactive
* **I/O Mapping Reference**: Built-in documentation

**Usage:**
```bash
./heizung3.py
```

#### heizung2.py (v3.9.1) - Data Logger

Automated data logging system for cron execution.

**Features:**
* **MySQL integration**: Automatic schema management (Schema V7)
* **Runtime persistence**: Stores runtime hours and cycle counts
* **MQTT publishing**: Real-time status updates
* **Schema versioning**: Automatic database schema updates
* **SQLAlchemy ORM**: Type-safe database operations
* **Error handling**: Robust connection management

**Cron Setup:**
```bash
# Log every 60 seconds
* * * * * ~/wago750-881/heizung2.py >> /var/log/heizung.log 2>&1
```

#### r290mb.py (v1.0.0) - R290 Heat Pump Logger

Modbus RTU data logger for Powerworld R290 heat pump with WAGO integration.

**Features:**
* **Complete Data Collection**:
  - Status and fault flags (11 registers)
  - Temperature sensors (8 measurements)
  - Technical parameters (compressor, fan, pump speeds)
  - Operating mode and parameters
* **Multi-Target Distribution**:
  - MySQL database logging (always active)
  - MQTT publishing (conditional)
  - WAGO PLC integration (tank temperature)
* **Conditional Transmission**: Only sends to MQTT/WAGO when tank temp > 0°C
* **Cross-System Optimization**: Shares R290 tank temp with WAGO for load balancing
* **Error Handling**: Complete validation and logging

**Hardware:**
- Connection: /dev/ttyUSB3 (USB-to-RS485 adapter)
- Protocol: Modbus RTU, 9600 baud, Slave ID 1
- Integration: Tank temp → WAGO register 12396 (%MW110)

**Usage:**
```bash
./r290mb.py

# Cron job (every 5 minutes)
*/5 * * * * ~/wago750-881/r290mb.py >> /var/log/r290mb.log 2>&1
```

**WAGO Integration:**
```st
(* Read R290 tank temperature in PLC *)
R290_Tank_Raw := xSetpoints[13];  (* Register 12396 *)
R290_Tank_Temp := INT_TO_REAL(R290_Tank_Raw) / 100.0;

(* Use for load optimization *)
IF (R290_Tank_Temp > 40.0) AND (temp_kessel < 50.0) THEN
    (* R290 has hot water, reduce oil boiler load *)
    bHK_Enable := FALSE;
END_IF;
```

#### wagostatus.py (v1.1.0) - Complete Status Overview

Comprehensive system diagnostic tool.

**Features:**
* **Physical I/O display**: Raw register values (%IW, %QB)
* **Complete variable mapping**: All xMeasure, xSetpoints, xSystem arrays
* **Calculated values**: Sample & hold sensor values after multiplexing
* **Modbus register documentation**: Full address mapping
* **System diagnostics**: Uptime, error counts, CPU load

### Supporting Scripts

* **wagoglobal.py** - Shared functions and constants
* **debug.py** - Troubleshooting and register debugging
* **reset_runtime.py** - Reset pump runtime counters

### Setup Scripts

* **setup_wago750.sh** - Initial PLC configuration
* **setupgit.sh** - Git repository setup with SSH

## Installation

### Prerequisites

```bash
# System packages
sudo apt-get update
sudo apt-get install python3 python3-pip git

# Python dependencies
pip3 install pymodbus pymysql paho-mqtt sqlalchemy pandas --break-system-packages

# For R290 heat pump (USB-to-RS485 access)
sudo usermod -a -G dialout $USER
# Logout and login again for group change
```

### PLC Setup

1. Open project in CoDeSys 2.3
2. Import `globalvar.st` (File → Import)
3. Import `heizung.st` (File → Import)
4. Compile project (F11)
5. Download to PLC (Online → Login)

**PLC Configuration:**
- IP Address: 192.168.1.100 (or your configured address)
- Modbus TCP Port: 502
- Slave ID: 0

### Python Scripts Setup

```bash
# Clone repository
cd ~
git clone git@github.com:gerontec/wago750-881.git
cd wago750-881

# Make scripts executable
chmod +x heizung2.py heizung3.py wagostatus.py r290mb.py reset_runtime.py

# Configure database connection in heizung2.py and r290mb.py
# Edit MySQL credentials and MQTT broker settings

# Test WAGO connection
./wagostatus.py

# Test R290 connection (if heat pump installed)
./r290mb.py
```

### Database Setup

```bash
# Create MySQL database
mysql -u root -p << EOF
CREATE DATABASE wagodb;
GRANT ALL PRIVILEGES ON wagodb.* TO 'heating'@'localhost' IDENTIFIED BY 'your_password';
FLUSH PRIVILEGES;
EOF

# Schemas will be created automatically on first run
# - heizung2.py creates heating_log table
# - r290mb.py creates heat_powerw table
```

## Modbus Register Mapping

### WAGO PLC Holding Registers (Slave 0)

#### Measurement Data (xMeasure[1..32]) – Starting at 12320 (%MW32 - %MW63)

| Address | PLC Variable | Description |
|---------|-------------|-------------|
| 12320 | %MW32 | Raw Analog Input %IW0 (Boiler temp sensor) |
| 12321 | %MW33 | Raw Analog Input %IW1 (HW tank sensor) |
| 12322 | %MW34 | Raw Analog Input %IW2 (HC flow sensor) |
| 12323 | %MW35 | Raw Analog Input %IW3 (Outdoor sensor) |
| 12324 | %MW36 | Digital Input %IW4 (8-channel DI card) |
| 12330 | %MW42 | Status Word (see bit mapping below) |
| 12336 | %MW48 | Hot Water Pump Runtime (hours) |
| 12337 | %MW49 | Hot Water Pump Cycles |
| 12338 | %MW50 | Heating Pump Runtime (hours) |
| 12339 | %MW51 | Heating Pump Cycles |
| 12340 | %MW52 | Well Pump Runtime (hours) |
| 12341 | %MW53 | Well Pump Cycles |
| 12344 | %MW54 | Hot Water Pump Reason Code |
| 12345 | %MW55 | Heating Pump Reason Code |
| 12346 | %MW56 | Well Pump Reason Code |
| 12351 | %MW63 | Physical Output Byte %QB0 |

**Status Word (%MW42) Bit Mapping:**
- Bit 0: WW Pump Active (compensates for inverted relay logic)
- Bit 1: HK Pump Active (compensates for inverted relay logic)
- Bit 2: Well Pump Active
- Bit 3: Night mode active
- Bit 4: Multiplexer Phase (0=A/8s, 1=B/51s)
- Bit 5: Data ready flag
- Bit 6: Sensor error
- Bit 7-15: Reserved

**Output Byte (%QB0 / Register 512) Bit Mapping:**
- Bit 0: Multiplexer Relay (switches sensor groups)
- Bit 1: Hot Water Pump (INVERTED LOGIC! LOW=ON via NC relay)
- Bit 2: Heating Pump (INVERTED LOGIC! LOW=ON via NC relay)
- Bit 3: Well Pump (direct control)
- Bit 4-7: Reserved

#### Setpoint Data (xSetpoints[1..16]) – Starting at 12384 (%MW96 - %MW111)

| Address | PLC Variable | Description |
|---------|-------------|-------------|
| 12384 | %MW96 | Hot Water Target Temperature (°C × 10) |
| 12385 | %MW97 | Heating Circuit Target Temp (°C × 10) |
| 12388 | %MW100 | Night Mode Start Hour |
| 12389 | %MW101 | Night Mode End Hour |
| 12396 | %MW108 | **R290 Tank Temperature** (°C × 100, from r290mb.py) |
| 12397 | %MW109 | Frost Protection Threshold (°C × 10) |
| 12398 | %MW110 | Tank Temperature (°C × 10) |
| 12402 | %MW114 | Hot Water Pump Override (0=Auto, 1=Force On, 2=Force Off) |
| 12403 | %MW115 | Heating Pump Override |
| 12404 | %MW116 | Well Pump Override |

#### System Diagnostics (xSystem[1..8]) – Starting at 12416 (%MW128 - %MW135)

| Address | PLC Variable | Description |
|---------|-------------|-------------|
| 12416 | %MW128 | Uptime Low Word (seconds) |
| 12417 | %MW129 | Uptime High Word (seconds) |
| 12418 | %MW130 | Error Count |
| 12419 | %MW131 | CPU Load (%) |

### R290 Heat Pump Modbus Registers (Slave 1, RS485)

See `R290_INTEGRATION.md` for complete register mapping.

**Key Registers:**
- 0x03-0x0D: Status and fault flags
- 0x0E-0x1C: Temperature sensors (inlet, tank, ambient, outlet, etc.)
- 0x1C-0x2F: Technical parameters (compressor, fan, pump speeds)
- 0x3F-0x43: Operating mode and parameters

## Usage Examples

### Interactive Monitoring

```bash
# Launch WAGO monitoring interface
./heizung3.py

# Monitor R290 heat pump
./r290mb.py

# Complete system status
./wagostatus.py

# Check runtime statistics
./wagostatus.py | grep -A 5 "Runtime"
```

### Override Control

```python
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient('192.168.1.100')

# Force hot water pump ON
client.write_register(12402, 1)

# Force heating pump OFF
client.write_register(12403, 2)

# Return to automatic mode
client.write_register(12402, 0)
client.write_register(12403, 0)

client.close()
```

### Cross-System Temperature Monitoring

```python
# Read both systems
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient('192.168.1.100')

# WAGO oil boiler temps
result = client.read_holding_registers(12336, 10)
boiler_temp = result.registers[0] / 100.0

# R290 heat pump tank temp (shared via r290mb.py)
result = client.read_holding_registers(12396, 1)
r290_tank = result.registers[0] / 100.0

print(f"Oil Boiler: {boiler_temp:.1f}°C")
print(f"R290 Tank: {r290_tank:.1f}°C")

client.close()
```

### Data Analysis

```sql
-- Average runtime per day (WAGO system)
SELECT 
    DATE(zeitstempel) as date,
    MAX(ww_pump_runtime) - MIN(ww_pump_runtime) as ww_daily_hours,
    MAX(hk_pump_runtime) - MIN(hk_pump_runtime) as hk_daily_hours
FROM heating_log 
WHERE zeitstempel > DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY DATE(zeitstempel)
ORDER BY date DESC;

-- R290 heat pump efficiency
SELECT 
    DATE(zeitstempel) as date,
    AVG(temp_tank) as avg_tank_temp,
    AVG(comp_power) as avg_power,
    COUNT(*) * 5 / 60 as runtime_hours
FROM heat_powerw
WHERE DATE(zeitstempel) = CURDATE()
AND comp_freq_actual > 0
GROUP BY DATE(zeitstempel);
```

## Troubleshooting

### Common Issues

**WAGO PLC not responding:**
```bash
# Check network connectivity
ping 192.168.1.100

# Test Modbus connection
./wagostatus.py

# Check PLC status LEDs
# - Green: Power OK
# - Yellow: Program running (should blink)
# - Red: Error state (should be OFF)
```

**R290 Heat Pump connection issues:**
```bash
# Check USB-to-RS485 adapter
ls -l /dev/ttyUSB*

# Check permissions
groups $USER  # Should include 'dialout'

# Test Modbus RTU connection
python3 -c "from pymodbus.client import ModbusSerialClient; \
    c = ModbusSerialClient(method='rtu', port='/dev/ttyUSB3', baudrate=9600); \
    print('Connected' if c.connect() else 'Failed'); c.close()"
```

**Python script errors:**
```bash
# Check dependencies
pip3 list | grep -E 'pymodbus|pymysql|paho-mqtt'

# Verify addresses in scripts
grep "WAGO_IP\|PLC_IP\|PORT" *.py

# Enable debug logging
MODBUS_DEBUG=1 ./heizung3.py
```

**Database connection issues:**
```bash
# Test MySQL connection
mysql -u heating -p wagodb

# Check schema versions
SELECT * FROM schema_version;

# View recent entries
SELECT * FROM heating_log ORDER BY zeitstempel DESC LIMIT 5;
SELECT * FROM heat_powerw ORDER BY zeitstempel DESC LIMIT 5;
```

## Project Structure

```
wago750-881/
├── README.md                    # This file
├── .gitignore                   # Git ignore rules
│
├── PLC Files/
│   ├── heizung.st              # Main PLC program (ST) v6.5.2
│   └── globalvar.st            # Global variables
│
├── Python Scripts/
│   ├── heizung2.py             # Data logger v3.9.1 (WAGO)
│   ├── heizung3.py             # Interactive monitor v4.1.0 (WAGO)
│   ├── r290mb.py               # R290 heat pump logger v1.0.0
│   ├── wagostatus.py           # Status overview v1.1.0
│   ├── wagoglobal.py           # Shared functions
│   ├── debug.py                # Debug utilities
│   └── reset_runtime.py        # Runtime reset tool
│
├── Documentation/
│   ├── io_reference.txt        # Complete I/O hardware reference
│   └── R290_INTEGRATION.md     # R290 heat pump integration guide
│
└── Setup Scripts/
    ├── setup_wago750.sh        # PLC setup script
    └── setupgit.sh             # Git configuration
```

## Version History

### Current Versions

- **PLC Program**: v6.5.2 (heizung.st)
- **Data Logger**: v3.9.1 (heizung2.py)
- **Monitor**: v4.1.0 (heizung3.py)
- **R290 Logger**: v1.0.0 (r290mb.py)
- **Status Tool**: v1.1.0 (wagostatus.py)
- **Database Schema**: V7 (heating_log)

### Recent Updates (January 2026)

**v6.5.2 (PLC):**
- Implemented OSCAT ACTUATOR_PUMP function blocks
- Added comprehensive reason code tracking
- Improved runtime counter reliability (NON-RETAIN)
- Enhanced override functionality with state validation
- Optimized ΔT calculation for better efficiency
- Added frost protection logic
- Implemented inverted relay logic for WW/HK pumps

**v4.1.0 (heizung3.py):**
- Complete physical I/O display (all analog/digital inputs)
- Bit-level output explanations with inverted relay logic
- Corrected output mapping (DO.0 = Multiplexer!)
- Enhanced status word decoding
- Added I/O mapping reference display
- Color-coded LED indicators
- Interactive override control menu

**v1.0.0 (r290mb.py):**
- NEW: Powerworld R290 heat pump integration
- Modbus RTU data collection (status, temps, technical params)
- MySQL database logging (heat_powerw table)
- MQTT publishing (r290/heatpump/all)
- WAGO PLC integration (tank temp to register 12396)
- Conditional transmission logic (only when tank > 0°C)
- Complete error handling and validation

## Cross-System Integration

### Load Balancing Strategy

The system uses R290 heat pump as primary heat source when available:

1. **R290 Priority**: Heat pump runs during mild weather (>5°C)
2. **Boiler Backup**: Oil boiler activates in cold weather or high demand
3. **Temperature Sharing**: R290 tank temp visible to WAGO PLC
4. **Smart Switching**: PLC reduces boiler load when R290 provides heat

### Data Flow

```
┌───────────────┐
│ R290 Heat Pump│
│  (Modbus RTU) │
└───────┬───────┘
        │ r290mb.py (every 5 min)
        ├─────────────┐
        ▼             ▼
   ┌─────────┐   ┌─────────┐
   │  MySQL  │   │  MQTT   │
   │ wagodb  │   │ Broker  │
   └─────────┘   └─────────┘
        │             │
        │             │ Tank Temp
        │             ▼
        │      ┌──────────────┐
        │      │  WAGO PLC    │
        │      │ (Reg 12396)  │
        │      └──────┬───────┘
        │             │
        │             │ heizung2.py (every 60s)
        │             ▼
        └──────►┌─────────┐
                │  MySQL  │
                │ heating │
                │  _log   │
                └─────────┘
```

## Development

### Adding New Features

To add new functionality to the PLC program:

1. Modify `globalvar.st` to add required variables
2. Update `heizung.st` with new control logic
3. Update Modbus register mapping if needed
4. Modify Python scripts to read new registers
5. Update database schema if logging new values
6. Test thoroughly before deploying

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Coding Standards

**Structured Text (PLC):**
- Use meaningful variable names (Hungarian notation)
- Comment all complex logic blocks
- Follow WAGO naming conventions
- Keep functions modular and reusable

**Python:**
- Follow PEP 8 style guide
- Use type hints where applicable
- Document all functions with docstrings
- Handle errors gracefully

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

* WAGO Kontakttechnik GmbH for the excellent PLC hardware
* OSCAT community for open-source PLC function blocks
* PyModbus developers for the robust Modbus library
* Powerworld for R290 heat pump documentation

## Contact

Project Link: [https://github.com/gerontec/wago750-881](https://github.com/gerontec/wago750-881)

## Additional Documentation

- **io_reference.txt**: Complete hardware I/O mapping and troubleshooting
- **R290_INTEGRATION.md**: Detailed R290 heat pump integration guide

---

**Last Updated**: January 6, 2026  
**Version**: 2.0.0  
**Maintainer**: gerontec
