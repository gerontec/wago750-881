(* ========================================================================== *)
(* GLOBALE KONSTANTEN                                                         *)
(* ========================================================================== *)
VAR_GLOBAL CONSTANT
    (* Heizkreis-Pumpe Reason Bits *)
    HK_REASON_FROSTSCHUTZ    : BYTE := 16#01;
    HK_REASON_WAERMEBEDARF   : BYTE := 16#02;
    HK_REASON_OVERRIDE       : BYTE := 16#04;

    (* Brunnenpumpe Reason Bits *)
    BR_REASON_HK_ACTIVE      : BYTE := 16#01;

    (* Sollwerte *)
    CONST_VL_SOLL_MIN : REAL := 45.0;

    (* NTC Boiler Kalibrierung *)
    NTC_BOILER_A : REAL := 40536.0;
    NTC_BOILER_B : REAL := 303.1;

    (* NTC Solar Kalibrierung *)
    NTC_SOLAR_A : REAL := 26402.0;
    NTC_SOLAR_B : REAL := 60.0;

    (* VERSION *)
    VERSION_MAJOR : BYTE := 6;
    VERSION_MINOR : BYTE := 5;
    VERSION_PATCH : BYTE := 2;
END_VAR

(* ========================================================================== *)
(* GLOBALE VARIABLEN                                                          *)
(* ========================================================================== *)
VAR_GLOBAL
    (* ====================================================================== *)
    (* PHYSIKALISCHE HARDWARE                                                 *)
    (* ====================================================================== *)
    analog0 AT %IW0 : WORD;
    analog1 AT %IW1 : WORD;
    analog2 AT %IW2 : WORD;
    analog3 AT %IW3 : WORD;
    DI8chan AT %IW4 : WORD;

    Output_0      AT %QX0.0 : BOOL;
    O1_WWPump     AT %QX0.1 : BOOL;
    O2_UmwaelzHK1 AT %QX0.2 : BOOL;
    O3_Brunnen    AT %QX0.3 : BOOL;
    O5            AT %QX0.5 : BOOL;

    (* ====================================================================== *)
    (* SAMPLE & HOLD SPEICHER                                                 *)
    (* ====================================================================== *)
    S_Vorlauf    : WORD;
    S_Aussen     : WORD;
    S_Innen      : WORD;
    S_Kessel     : WORD;
    S_Warmw      : WORD;
    S_Oeltank    : WORD;
    S_Ruecklauf  : WORD;
    S_Solar      : WORD;

    (* ====================================================================== *)
    (* BERECHNETE WERTE                                                       *)
    (* ====================================================================== *)
    (* Temperaturen *)
    temp_vorlauf   : REAL;
    temp_kessel    : REAL;
    temp_aussen    : REAL;
    temp_innen     : REAL;
    temp_ruecklauf : REAL;
    temp_warmw     : REAL;
    temp_solar     : REAL;
    temp_diff_ww   : REAL;

    (* Hilfsvariablen für Sensorberechnung *)
    ohm_vorlauf   : REAL;
    ohm_kessel    : REAL;
    ohm_aussen    : REAL;
    ohm_innen     : REAL;
    ohm_ruecklauf : REAL;
    raw_warmw_real : REAL;
    raw_solar_real : REAL;

    (* PT1000 Kalibrierung *)
    PT1000_R0  : REAL := 1000.0;
    R_Mess     : REAL := 10000.0;
    U_Vers     : REAL := 24.0;
    U_SPS      : REAL := 10.0;
    Raw_Max    : REAL := 32767.0;
    U_PT       : REAL;

    (* ====================================================================== *)
    (* STEUERUNG                                                              *)
    (* ====================================================================== *)
    bSensorError      : BOOL := FALSE;
    bNachtAbsenkung   : BOOL := FALSE;
    bDataReady        : BOOL := FALSE;
    mux_state         : BOOL := FALSE;

    (* Reason Bytes *)
    bWW_Reason : BYTE := 0;
    bHK_Reason : BYTE := 0;
    bBR_Reason : BYTE := 0;

    (* Enable/Manual Signale für Pumpen *)
    bWW_Enable : BOOL := FALSE;
    bHK_Enable : BOOL := FALSE;
    bBR_Enable : BOOL := FALSE;

    bWW_Manual : BOOL := FALSE;
    bHK_Manual : BOOL := FALSE;
    bBR_Manual : BOOL := FALSE;

    (* Echtzeituhr *)
    rtc_dt      : DT;
    hour_of_day : INT;

    (* Nachtabsenkungszeiten *)
    nacht_start_hour : INT := 23;
    nacht_end_hour   : INT := 4;

    (* Timer *)
    Timer_Long   : TON;
    Timer_Short  : TON;
    Timer_Settle : TON;

    (* ====================================================================== *)
    (* OSCAT BUILDING ACTUATOR_PUMP INSTANZEN                                *)
    (* ====================================================================== *)
    ACTUATOR_WW : ACTUATOR_PUMP;
    ACTUATOR_HK : ACTUATOR_PUMP;
    ACTUATOR_BR : ACTUATOR_PUMP;

    (* ====================================================================== *)
    (* BETRIEBSSTUNDEN - NON-RETAIN                                          *)
    (* ====================================================================== *)
    WW_Runtime : UDINT := 0;  (* Hundertstel-Sekunden *)
    WW_Cycles  : UDINT := 0;  (* Anzahl Starts *)
    HK_Runtime : UDINT := 0;
    HK_Cycles  : UDINT := 0;
    BR_Runtime : UDINT := 0;
    BR_Cycles  : UDINT := 0;

    (* ====================================================================== *)
    (* MODBUS-REGISTER - MEMORY MAPPING                                      *)
    (* ====================================================================== *)
    (* WICHTIG: Modbus-Adresse = CODESYS MW-Nummer + 12288                   *)
    (*                                                                        *)
    (* Beispiel: MW32 = Modbus-Adresse 12320                                 *)
    (*           MW96 = Modbus-Adresse 12384                                 *)
    (* ====================================================================== *)

    (* MW0-31: Basis-Zähler (deprecated, für Kompatibilität) *)
    xNewVar7 AT %MW0 : ARRAY [1..16] OF INT;
    (* [1] = Zaehler_kWh (deprecated)
       [2] = Zaehler_Pumpe (deprecated)
       [3] = Zaehler_Brunnen (deprecated)
       [4-16] = Reserve *)

    (* ====================================================================== *)
    (* MW32-63: MESSWERTE & STATUS (Modbus 12320-12351)                      *)
    (* ====================================================================== *)
    xMeasure AT %MW32 : ARRAY [1..32] OF INT;
    (* [1]  = MW32  = 12320 = S_Vorlauf (Raw WORD)
       [2]  = MW33  = 12321 = S_Aussen (Raw WORD)
       [3]  = MW34  = 12322 = S_Innen (Raw WORD)
       [4]  = MW35  = 12323 = S_Kessel (Raw WORD)
       [5]  = MW36  = 12324 = S_Warmw (Raw WORD)
       [6]  = MW37  = 12325 = S_Oeltank (Raw WORD)
       [7]  = MW38  = 12326 = S_Ruecklauf (Raw WORD)
       [8]  = MW39  = 12327 = S_Solar (Raw WORD)
       [9]  = MW40  = 12328 = DI8chan (Raw WORD)
       [10] = MW41  = 12329 = hour_of_day (INT 0-23)
       [11] = MW42  = 12330 = Status-Word (INT Bitmaske)
            Bit 0: O1_WWPump aktiv
            Bit 1: O2_UmwaelzHK1 aktiv
            Bit 2: O3_Brunnen aktiv
            Bit 3: bNachtAbsenkung aktiv
            Bit 4: mux_state (Phase A/B)
            Bit 5: bDataReady
            Bit 6: bSensorError
       [12] = MW43  = 12331 = temp_diff_ww * 100 (INT, z.B. 1087 = 10.87°C)
       [13] = MW44  = 12332 = temp_kessel * 100 (INT)
       [14] = MW45  = 12333 = temp_warmw * 100 (INT)
       [15] = MW46  = 12334 = temp_vorlauf * 100 (INT)
       [16] = MW47  = 12335 = VERSION (Byte-Packed: High=Major, Low=Minor)
       [17] = MW48  = 12336 = VERSION_PATCH (INT)
       [18] = MW49  = 12337 = Seriennummer (INT, fixiert auf 15)
       [19] = MW50  = 12338 = WW_Runtime in Sekunden (INT, max 32767s)
       [20] = MW51  = 12339 = HK_Runtime in Sekunden (INT, max 32767s)
       [21] = MW52  = 12340 = BR_Runtime in Sekunden (INT, max 32767s)
       [22] = MW53  = 12341 = WW_Cycles (INT, Anzahl Starts)
       [23] = MW54  = 12342 = HK_Cycles (INT, Anzahl Starts)
       [24] = MW55  = 12343 = BR_Cycles (INT, Anzahl Starts)
       [25] = MW56  = 12344 = bWW_Reason (INT, Low-Byte = Bitmaske)
       [26] = MW57  = 12345 = bHK_Reason (INT, Low-Byte = Bitmaske)
       [27] = MW58  = 12346 = bBR_Reason (INT, Low-Byte = Bitmaske)
       [28] = MW59  = 12347 = temp_aussen * 100 (INT)
       [29] = MW60  = 12348 = temp_innen * 100 (INT)
       [30] = MW61  = 12349 = temp_ruecklauf * 100 (INT)
       [31] = MW62  = 12350 = temp_solar * 100 (INT)
       [32] = MW63  = 12351 = QB0 Physical Output Byte (INT) *)

    (* ====================================================================== *)
    (* MW96-111: SETPOINTS & KONFIGURATION (Modbus 12384-12399)              *)
    (* ====================================================================== *)
    xSetpoints AT %MW96 : ARRAY [1..16] OF INT;
    (* [1]  = MW96  = 12384 = Soll-Temperatur Vorlauf * 100 (4500 = 45.0°C)
       [2]  = MW97  = 12385 = Soll-Temperatur Warmwasser * 100
       [3]  = MW98  = 12386 = Hysterese Vorlauf * 100
       [4]  = MW99  = 12387 = Hysterese Warmwasser * 100
       [5]  = MW100 = 12388 = Nachtabsenkung Start (Stunde 0-23, -1=nicht gesetzt)
       [6]  = MW101 = 12389 = Nachtabsenkung Ende (Stunde 0-23, -1=nicht gesetzt)
       [7]  = MW102 = 12390 = Nachtabsenkung Temperatur * 100
       [8]  = MW103 = 12391 = Multiplexer Zeit Phase A (Sekunden)
       [9]  = MW104 = 12392 = Multiplexer Zeit Phase B (Sekunden)
       [10] = MW105 = 12393 = Frostschutz-Schwelle * 100 (-1300 = -13.0°C, 0=nicht gesetzt)
       [11] = MW106 = 12394 = Max Vorlauf * 100
       [12] = MW107 = 12395 = Pumpen Nachlaufzeit (Sekunden)
       [13] = MW108 = 12396 = HeatPump R290 Watertank Temp * 100 (von Python geschrieben)
       [14] = MW109 = 12397 = Pumpen-Override WW (-1=Force OFF, 0=Auto, 1=Force ON)
       [15] = MW110 = 12398 = Pumpen-Override HK (-1=Force OFF, 0=Auto, 1=Force ON)
       [16] = MW111 = 12399 = Pumpen-Override Brunnen (-1=Force OFF, 0=Auto, 1=Force ON) *)

    (* ====================================================================== *)
    (* MW128-135: SYSTEM-DIAGNOSE (Modbus 12416-12423)                       *)
    (* ====================================================================== *)
    xSystem AT %MW128 : ARRAY [1..8] OF INT;
    (* [1] = MW128 = 12416 = Uptime Sekunden (low word, 0-65535)
       [2] = MW129 = 12417 = Uptime Sekunden (high word) ? 32-bit kombiniert
       [3] = MW130 = 12418 = Fehler-Counter
       [4] = MW131 = 12419 = CPU Load %
       [5] = MW132 = 12420 = Cycle time min (ms)
       [6] = MW133 = 12421 = Cycle time max (ms)
       [7] = MW134 = 12422 = Cycle time avg (ms)
       [8] = MW135 = 12423 = Reserve *)

    (* ====================================================================== *)
    (* MW144-151: ALARM-REGISTER (Modbus 12432-12439)                        *)
    (* ====================================================================== *)
    xAlarms AT %MW144 : ARRAY [1..8] OF INT;
    (* [1] = MW144 = 12432 = Alarm-Bitmaske
            Bit 0: Sensor Vorlauf Fehler
            Bit 1: Sensor Aussen Fehler
            Bit 2: Sensor Kessel Fehler
            Bit 3: Sensor WW Fehler
            Bit 4-15: Reserve
       [2] = MW145 = 12433 = Fehler-Counter Sensor Vorlauf
       [3] = MW146 = 12434 = Fehler-Counter Sensor Aussen
       [4] = MW147 = 12435 = Fehler-Counter Sensor Kessel
       [5] = MW148 = 12436 = Fehler-Counter Sensor WW
       [6-8] = Reserve *)

    (* ====================================================================== *)
    (* MW160-167: STATISTIK (Modbus 12448-12455)                             *)
    (* ====================================================================== *)
    xStats AT %MW160 : ARRAY [1..8] OF INT;
    (* [1] = MW160 = 12448 = Betriebsstunden HK (Stunden)
       [2] = MW161 = 12449 = Betriebsstunden WW (Stunden)
       [3] = MW162 = 12450 = Betriebsstunden BR (Stunden)
       [4] = MW163 = 12451 = Starts HK
       [5] = MW164 = 12452 = Starts WW
       [6] = MW165 = 12453 = Starts BR
       [7] = MW166 = 12454 = Reserve
       [8] = MW167 = 12455 = Reserve *)

    (* ====================================================================== *)
    (* HILFSVARIABLEN                                                         *)
    (* ====================================================================== *)
    uptime_seconds : UDINT := 0;
    error_counter : INT := 0;
    QB0_shadow : BYTE;  (* Kopie von %QB0 für Modbus *)
END_VAR

(* ========================================================================== *)
(* REGISTER-MAPPING ZUSAMMENFASSUNG                                          *)
(* ========================================================================== *)
(*
WICHTIGE ADRESSEN FÜR PYTHON:

Stunden-Setpoint schreiben:
  MW0 = 12288 (hour_of_day wird von Python geschrieben)

Messwerte lesen:
  MW32-63 = 12320-12351 (xMeasure[1..32])
  
Setpoints schreiben:
  MW96-111 = 12384-12399 (xSetpoints[1..16])
  
  Wichtigste:
    MW100 = 12388 = Nachtabsenkung Start
    MW101 = 12389 = Nachtabsenkung Ende
    MW105 = 12393 = Frostschutz-Schwelle
    MW108 = 12396 = R290 Wassertank Temp
    MW109 = 12397 = WW Override
    MW110 = 12398 = HK Override
    MW111 = 12399 = BR Override

Physical Outputs lesen:
  %QB0 = 512 (Physical Output Byte)

System-Info lesen:
  MW128-135 = 12416-12423 (xSystem[1..8])
*)
