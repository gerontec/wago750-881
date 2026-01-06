# WAGO 750-881 Heating Control System

Professional heating control system for WAGO 750-881 PLC with Python monitoring and MySQL data logging.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![PLC](https://img.shields.io/badge/PLC-WAGO%20750--881-orange.svg)](https://www.wago.com)
[![Python](https://img.shields.io/badge/python-3.x-blue.svg)](https://www.python.org)

## Overview

Control system for oil heating with 3 pumps (hot water, heating circuit, well pump) featuring temperature-based control logic, override functionality, and comprehensive monitoring via Modbus TCP.

### Hardware Configuration

* **PLC**: WAGO 750-881 (Modbus TCP Master)
* **Sensors**: 
  - 5× PT1000 temperature sensors (boiler, hot water, heating circuit, outdoor, return)
  - 2× NTC temperature sensors (multiplexed)
  - 1× Oil tank level sensor
* **Outputs**: 3× Pump relays + Multiplexer control
* **Inputs**: 8-channel digital input card

## System Components

### PLC Program (v6.4.8)

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
* **Fail-safe design**: All critical functions have safety fallbacks

**Control Logic:**
- Hot water pump: Boiler > HW tank + 2°C
- Heating pump: Boiler > HC flow + 2°C  
- Well pump: Linked to heating pump operation
- All pumps respect override settings and safety limits

### Python Scripts

#### heizung3.py (v3.8.3) - Interactive Monitoring

Manual monitoring tool with real-time status display.

**Features:**
* **Graphical DI/DO display**: Visual representation of all inputs/outputs
* **Runtime statistics**: Per-pump runtime hours and cycle counts
* **Override control**: Interactive pump override management
* **LED test mode**: Test all outputs
* **Temperature monitoring**: All sensor values with formatting
* **Reason code display**: Shows why each pump is active/inactive
* **Status word decoding**: Multiplexer phase, night mode, errors

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
* **Pandas integration**: Efficient data processing

**Database Schema V7:**
- Timestamp tracking
- All temperature sensors
- Pump states and runtime
- Cycle counters
- Reason codes
- Override states
- System status word

**Cron Setup:**
```bash
# Log every 60 seconds
* * * * * ~/wago750-881/heizung2.py >> /var/log/heizung.log 2>&1
```

#### wagostatus.py (v1.1.0) - Complete Status Overview

Comprehensive system diagnostic tool.

**Features:**
* **Physical I/O display**: Raw register values (%IW, %QB)
* **Complete variable mapping**: All xMeasure, xSetpoints, xSystem arrays
* **Calculated values**: Sample & hold sensor values after multiplexing
* **Modbus register documentation**: Full address mapping
* **System diagnostics**: Uptime, error counts, CPU load

**Usage:**
```bash
./wagostatus.py
```

#### Supporting Scripts

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
```

### PLC Setup

1. Open project in CoDeSys 2.3
2. Import `globalvar.st` (File → Import)
3. Import `heizung.st` (File → Import)
4. Compile project (F11)
5. Download to PLC (Online → Login)

**PLC Configuration:**
- IP Address: 192.168.1.100 (default)
- Modbus TCP Port: 502
- Slave ID: 0

### Python Scripts Setup

```bash
# Clone repository
cd ~
git clone git@github.com:gerontec/wago750-881.git
cd wago750-881

# Make scripts executable
chmod +x heizung2.py heizung3.py wagostatus.py reset_runtime.py

# Configure database connection in heizung2.py
# Edit MySQL credentials and MQTT broker settings

# Test connection
./wagostatus.py
```

### Database Setup

```bash
# Create MySQL database
mysql -u root -p << EOF
CREATE DATABASE heating_control;
GRANT ALL PRIVILEGES ON heating_control.* TO 'heating'@'localhost' IDENTIFIED BY 'your_password';
FLUSH PRIVILEGES;
EOF

# Schema will be created automatically by heizung2.py on first run
```

## Modbus Register Mapping

### Holding Registers (Slave 0)

#### Measurement Data (xMeasure[1..32]) – Starting at 12320 (%MW32 - %MW63)

| Address | PLC Variable | Description |
|---------|-------------|-------------|
| 12320 | %MW32 | Raw Analog Input %IW0 (0-32767) |
| 12321 | %MW33 | Raw Analog Input %IW1 |
| 12322 | %MW34 | Raw Analog Input %IW2 |
| 12323 | %MW35 | Raw Analog Input %IW3 |
| 12324 | %MW36 | Digital Input %IW4 (DI8chan) |
| 12330 | %MW42 | Status Word (see below) |
| 12336 | %MW48 | Hot Water Pump Runtime (hours) |
| 12337 | %MW49 | Hot Water Pump Cycles |
| 12338 | %MW50 | Heating Pump Runtime (hours) |
| 12339 | %MW51 | Heating Pump Cycles |
| 12340 | %MW52 | Well Pump Runtime (hours) |
| 12341 | %MW53 | Well Pump Cycles |
| 12342 | %MW54 | Reserved |
| 12343 | %MW55 | Reserved |
| 12344 | %MW56 | Hot Water Pump Reason Code |
| 12345 | %MW57 | Heating Pump Reason Code |
| 12346 | %MW58 | Well Pump Reason Code |
| 12347 | %MW59 | Reserved Reason Code |
| 12351 | %MW63 | Physical Output Byte %QB0 |

**Status Word (%MW42) Bit Mapping:**
- Bit 0-2: Reserved
- Bit 3: Night mode active
- Bit 4: Multiplexer Phase (0=A, 1=B)
- Bit 5: Data ready flag
- Bit 6: Sensor error
- Bit 7-15: Reserved

**Reason Codes:**
- 0x00: Off - No demand
- 0x01: On - ΔT threshold exceeded
- 0x02: On - Override active
- 0x03: Off - Override inactive
- 0x04: Off - Safety limit
- 0x05: On - Frost protection
- 0x06: Off - Night mode

#### Setpoint Data (xSetpoints[1..16]) – Starting at 12384 (%MW96 - %MW111)

| Address | PLC Variable | Description |
|---------|-------------|-------------|
| 12384 | %MW96 | Hot Water Target Temperature (°C × 10) |
| 12385 | %MW97 | Heating Circuit Target Temp (°C × 10) |
| 12388 | %MW100 | Night Mode Start Hour |
| 12389 | %MW101 | Night Mode End Hour |
| 12397 | %MW109 | Frost Protection Threshold (°C × 10) |
| 12398 | %MW110 | Tank Temperature (°C × 10) |
| 12400 | %MW112 | Hot Water Pump Override (0=Auto, 1=Force On, 2=Force Off) |
| 12401 | %MW113 | Heating Pump Override |
| 12402 | %MW114 | Well Pump Override |
| 12403 | %MW115 | Reserved Override |

#### System Diagnostics (xSystem[1..8]) – Starting at 12416 (%MW128 - %MW135)

| Address | PLC Variable | Description |
|---------|-------------|-------------|
| 12416 | %MW128 | Uptime Low Word (seconds) |
| 12417 | %MW129 | Uptime High Word (seconds) |
| 12418 | %MW130 | Error Count |
| 12419 | %MW131 | CPU Load (%) |
| 12420-12423 | %MW132-135 | Reserved for future use |

### Output Register Mapping

| Address | PLC Variable | Description |
|---------|-------------|-------------|
| 512 | %QB0 | Physical output byte (direct relay control) |

**%QB0 Bit Mapping:**
- Bit 0: Hot Water Pump
- Bit 1: Heating Circuit Pump
- Bit 2: Well Pump
- Bit 3: Multiplexer Control A
- Bit 4: Multiplexer Control B
- Bit 5-7: Reserved

## Usage Examples

### Interactive Monitoring

```bash
# Launch real-time monitoring interface
./heizung3.py

# Monitor specific pump
./heizung3.py | grep "Hot Water"

# Check runtime statistics
./wagostatus.py | grep -A 5 "Runtime"
```

### Override Control

```python
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient('192.168.1.100')

# Force hot water pump ON
client.write_register(12400, 1)

# Force heating pump OFF
client.write_register(12401, 2)

# Return to automatic mode
client.write_register(12400, 0)
client.write_register(12401, 0)

client.close()
```

### Data Analysis

```python
import pymysql
import pandas as pd

# Connect to database
conn = pymysql.connect(
    host='localhost',
    user='heating',
    password='your_password',
    database='heating_control'
)

# Query runtime data
df = pd.read_sql("""
    SELECT timestamp, 
           ww_pump_runtime, 
           hk_pump_runtime,
           ww_pump_cycles
    FROM heating_log 
    WHERE timestamp > DATE_SUB(NOW(), INTERVAL 7 DAY)
""", conn)

# Calculate daily runtime
daily_runtime = df.groupby(df['timestamp'].dt.date).agg({
    'ww_pump_runtime': 'max',
    'hk_pump_runtime': 'max'
})

print(daily_runtime)
```

## Troubleshooting

### Common Issues

**PLC not responding:**
```bash
# Check network connectivity
ping 192.168.1.100

# Test Modbus connection
./wagostatus.py

# Check PLC status LEDs
# - Green: Power OK
# - Yellow: Program running
# - Red: Error state
```

**Python script errors:**
```bash
# Check dependencies
pip3 list | grep -E 'pymodbus|pymysql|paho-mqtt'

# Verify PLC address in scripts
grep "ModbusTcpClient" *.py

# Enable debug logging
MODBUS_DEBUG=1 ./heizung3.py
```

**Database connection issues:**
```bash
# Test MySQL connection
mysql -u heating -p heating_control

# Check schema version
SELECT * FROM schema_version;

# Repair tables if needed
mysqlcheck -u heating -p --auto-repair heating_control
```

**Runtime counter reset:**
```bash
# Reset all runtime counters
./reset_runtime.py

# Reset specific pump (edit script as needed)
# Writes 0 to runtime registers 12336-12341
```

## Project Structure

```
wago750-881/
├── README.md                 # This file
├── .gitignore               # Git ignore rules
│
├── PLC Files/
│   ├── heizung.st           # Main PLC program (ST)
│   └── globalvar.st         # Global variables
│
├── Python Scripts/
│   ├── heizung2.py          # Data logger (v3.9.1)
│   ├── heizung3.py          # Interactive monitor (v3.8.3)
│   ├── wagostatus.py        # Status overview (v1.1.0)
│   ├── wagoglobal.py        # Shared functions
│   ├── debug.py             # Debug utilities
│   └── reset_runtime.py     # Runtime reset tool
│
└── Setup Scripts/
    ├── setup_wago750.sh     # PLC setup script
    └── setupgit.sh          # Git configuration
```

## Version History

### Current Versions

- **PLC Program**: v6.4.8 (heizung.st)
- **Data Logger**: v3.9.1 (heizung2.py)
- **Monitor**: v3.8.3 (heizung3.py)
- **Status Tool**: v1.1.0 (wagostatus.py)
- **Database Schema**: V7

### Recent Updates (January 2026)

**v6.4.8 (PLC):**
- Implemented OSCAT ACTUATOR_PUMP function blocks
- Added comprehensive reason code tracking
- Improved runtime counter reliability (NON-RETAIN)
- Enhanced override functionality with state validation
- Optimized ΔT calculation for better efficiency
- Added frost protection logic

**v3.9.1 (heizung2.py):**
- Upgraded to Database Schema V7
- Added automatic schema migration
- Implemented MQTT status publishing
- Enhanced error handling and logging
- Added runtime and cycle counter persistence
- SQLAlchemy ORM integration

**v3.8.3 (heizung3.py):**
- Improved graphical status display
- Added reason code visualization
- Enhanced override control interface
- Better error message formatting
- Real-time status word decoding

**v1.1.0 (wagostatus.py):**
- Complete Modbus register documentation
- Physical I/O display with raw values
- System diagnostics display
- Enhanced variable mapping
- Sample & hold value calculation

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

## Contact

Project Link: [https://github.com/gerontec/wago750-881](https://github.com/gerontec/wago750-881)

## Appendix

### Temperature Sensor Mapping

| Sensor | Type | Location | Register |
|--------|------|----------|----------|
| T1 | PT1000 | Boiler | %IW0 → Sample & Hold |
| T2 | PT1000 | Hot Water Tank | %IW1 → Sample & Hold |
| T3 | PT1000 | Heating Circuit | %IW2 → Sample & Hold |
| T4 | PT1000 | Outdoor | %IW3 → Sample & Hold |
| T5 | PT1000 | Return Flow | Multiplexed Phase A |
| T6 | NTC | Auxiliary 1 | Multiplexed Phase B |
| T7 | NTC | Auxiliary 2 | Multiplexed Phase B |

### Typical Temperature Values

- Boiler: 60-80°C (operational), 40-60°C (standby)
- Hot Water Tank: 45-60°C (target)
- Heating Circuit: 30-50°C (depending on outdoor temp)
- Outdoor: -20 to +40°C
- Return Flow: 30-45°C

### Safety Features

* **Overheat Protection**: Pump shutdown at >85°C boiler temp
* **Frost Protection**: Automatic pump activation at <5°C
* **Sensor Error Handling**: Safe mode operation if sensor fails
* **Override Safety**: Timeout limits on manual overrides
* **Fail-Safe Outputs**: All outputs OFF on PLC error

### MQTT Topics

```
heating/status              # General status (JSON)
heating/temperatures        # All temperature sensors
heating/pumps/hotwater      # Hot water pump state
heating/pumps/heating       # Heating pump state
heating/pumps/well          # Well pump state
heating/runtime             # Runtime statistics
heating/errors              # Error messages
```

---

**Last Updated**: January 6, 2026  
**Version**: 1.2.0  
**Maintainer**: gerontec
