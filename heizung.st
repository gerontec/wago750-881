(* ========================================================================== *)
(* PLC_PRG - HAUPTPROGRAMM v6.5.2                                            *)
(* ========================================================================== *)

(* Initialisierung *)
bWW_Reason := 0;
bHK_Reason := 0;
bBR_Reason := 0;
xAlarms[1] := 0;

(* ========================================================================== *)
(* 1. ECHTZEITUHR & NACHTABSENKUNG - DYNAMISCH                              *)
(* ========================================================================== *)
rtc_dt := SysRtcGetTime(TRUE);
hour_of_day := DWORD_TO_INT((DT_TO_DWORD(rtc_dt) / 3600) MOD 24);

(* Nachtabsenkungszeiten aus xSetpoints[5] und [6] lesen *)
IF (xSetpoints[5] < 0) OR (xSetpoints[5] > 23) OR (xSetpoints[6] < 0) OR (xSetpoints[6] > 23) THEN
    (* Ungültige Werte -> DEAKTIVIERT *)
    bNachtAbsenkung := FALSE;
ELSIF (xSetpoints[5] = 0) AND (xSetpoints[6] = 0) THEN
    (* Beide 0 = nicht initialisiert -> DEAKTIVIERT *)
    bNachtAbsenkung := FALSE;
ELSE
    (* Gültige Werte übernehmen *)
    nacht_start_hour := xSetpoints[5];
    nacht_end_hour := xSetpoints[6];
    
    (* Nachtabsenkung berechnen *)
    IF nacht_start_hour < nacht_end_hour THEN
        (* Normal: z.B. 6-10 Uhr *)
        bNachtAbsenkung := (hour_of_day >= nacht_start_hour) AND (hour_of_day < nacht_end_hour);
    ELSE
        (* Über Mitternacht: z.B. 23-4 Uhr *)
        bNachtAbsenkung := (hour_of_day >= nacht_start_hour) OR (hour_of_day < nacht_end_hour);
    END_IF;
END_IF;

(* ========================================================================== *)
(* 2. MULTIPLEXER                                                             *)
(* ========================================================================== *)
IF mux_state THEN
    Timer_Long(IN := TRUE, PT := T#51S);
    IF Timer_Long.Q THEN
        mux_state := FALSE;
        Timer_Long(IN := FALSE);
        Timer_Settle(IN := FALSE);
    END_IF;
ELSE
    Timer_Short(IN := TRUE, PT := T#8S);
    IF Timer_Short.Q THEN
        mux_state := TRUE;
        Timer_Short(IN := FALSE);
        Timer_Settle(IN := FALSE);
    END_IF;
END_IF;

Output_0 := mux_state;
Timer_Settle(IN := TRUE, PT := T#2S);
bDataReady := Timer_Settle.Q;

(* ========================================================================== *)
(* 3. SAMPLE & HOLD                                                           *)
(* ========================================================================== *)
IF bDataReady THEN
    IF mux_state THEN
        S_Vorlauf := analog0;
        S_Aussen  := analog1;
        S_Innen   := analog2;
        S_Kessel  := analog3;
    ELSE
        S_Warmw     := analog0;
        S_Oeltank   := analog1;
        S_Ruecklauf := analog2;
        S_Solar     := analog3;
    END_IF;
END_IF;

(* ========================================================================== *)
(* 4. TEMPERATUR-BERECHNUNGEN                                                 *)
(* ========================================================================== *)
U_PT := (WORD_TO_REAL(S_Vorlauf) / Raw_Max) * U_SPS;
ohm_vorlauf := (U_PT * R_Mess) / (U_Vers - U_PT);
temp_vorlauf := TEMP_PT(ohm_vorlauf, PT1000_R0);

U_PT := (WORD_TO_REAL(S_Kessel) / Raw_Max) * U_SPS;
ohm_kessel := (U_PT * R_Mess) / (U_Vers - U_PT);
temp_kessel := TEMP_PT(ohm_kessel, PT1000_R0);

U_PT := (WORD_TO_REAL(S_Aussen) / Raw_Max) * U_SPS;
ohm_aussen := (U_PT * R_Mess) / (U_Vers - U_PT);
temp_aussen := TEMP_PT(ohm_aussen, PT1000_R0);

U_PT := (WORD_TO_REAL(S_Innen) / Raw_Max) * U_SPS;
ohm_innen := (U_PT * R_Mess) / (U_Vers - U_PT);
temp_innen := TEMP_PT(ohm_innen, PT1000_R0);

U_PT := (WORD_TO_REAL(S_Ruecklauf) / Raw_Max) * U_SPS;
ohm_ruecklauf := (U_PT * R_Mess) / (U_Vers - U_PT);
temp_ruecklauf := TEMP_PT(ohm_ruecklauf, PT1000_R0);

raw_warmw_real := WORD_TO_REAL(S_Warmw);
IF (raw_warmw_real >= 4000.0) AND (raw_warmw_real <= 45000.0) THEN
    temp_warmw := (NTC_BOILER_A - raw_warmw_real) / NTC_BOILER_B;
ELSE
    temp_warmw := 0.0;
END_IF;

raw_solar_real := WORD_TO_REAL(S_Solar);
IF (raw_solar_real >= 4000.0) AND (raw_solar_real <= 40000.0) THEN
    temp_solar := (raw_solar_real - NTC_SOLAR_A) / NTC_SOLAR_B;
ELSE
    temp_solar := 0.0;
END_IF;

temp_diff_ww := temp_kessel - temp_warmw;
bSensorError := FALSE;

(* ========================================================================== *)
(* 5. PUMPENSTEUERUNG - MIT INVERTIERTER RELAIS-LOGIK                       *)
(* ========================================================================== *)
watertank_waschk := xSetpoints[13];

(* ========================================================================== *)
(* 5.1 WARMWASSER-PUMPE - IGNORIERT NACHTABSENKUNG!                         *)
(* ========================================================================== *)
bWW_Reason := BYTE#0;

(* Temperaturdifferenz - OHNE Nachtabsenkungsprüfung *)
IF temp_diff_ww >= 2.0 THEN
    bWW_Reason := BYTE#1;  (* WW_REASON_TEMP_DIFF *)
END_IF;

(* Override-Handling *)
IF xSetpoints[14] < INT#0 THEN
    bWW_Enable := FALSE;
    bWW_Manual := TRUE;
    bWW_Reason := BYTE#0;
ELSIF xSetpoints[14] > INT#0 THEN
    bWW_Enable := TRUE;
    bWW_Manual := TRUE;
    bWW_Reason := BYTE#4;  (* WW_REASON_OVERRIDE *)
ELSE
    bWW_Enable := (bWW_Reason > BYTE#0);
    bWW_Manual := FALSE;
END_IF;

ACTUATOR_WW(
    IN := bWW_Enable,
    MANUAL := bWW_Manual,
    RST := FALSE,
    MIN_ONTIME := T#120S,
    MIN_OFFTIME := T#60S,
    RUN_EVERY := T#10000M,
    RUNTIME := WW_Runtime,
    CYCLES := WW_Cycles
);

(* Invertierte Relais-Logik *)
IF xSetpoints[14] < INT#0 THEN
    O1_WWPump := NOT FALSE;
ELSIF xSetpoints[14] > INT#0 THEN
    O1_WWPump := NOT TRUE;
ELSE
    O1_WWPump := NOT ACTUATOR_WW.PUMP;
END_IF;

(* ========================================================================== *)
(* 5.2 HEIZKREIS-PUMPE - BEACHTET NACHTABSENKUNG                            *)
(* ========================================================================== *)
bHK_Reason := BYTE#0;

(* Frostschutz - dynamisch aus xSetpoints[10] *)
IF xSetpoints[10] <> 0 THEN
    IF temp_aussen < (INT_TO_REAL(xSetpoints[10]) / 100.0) THEN
        bHK_Reason := HK_REASON_FROSTSCHUTZ;
    END_IF;
END_IF;

(* Wärmebedarf nur außerhalb Nachtabsenkung *)
IF (temp_vorlauf < CONST_VL_SOLL_MIN) AND NOT bNachtAbsenkung THEN
    bHK_Reason := bHK_Reason OR HK_REASON_WAERMEBEDARF;
END_IF;

(* Override-Handling *)
IF xSetpoints[15] < INT#0 THEN
    bHK_Enable := FALSE;
    bHK_Manual := TRUE;
    bHK_Reason := BYTE#0;
ELSIF xSetpoints[15] > INT#0 THEN
    bHK_Enable := TRUE;
    bHK_Manual := TRUE;
    bHK_Reason := bHK_Reason OR HK_REASON_OVERRIDE;
ELSE
    bHK_Enable := (bHK_Reason > BYTE#0);
    bHK_Manual := FALSE;
END_IF;

ACTUATOR_HK(
    IN := bHK_Enable,
    MANUAL := bHK_Manual,
    RST := FALSE,
    MIN_ONTIME := T#5M,
    MIN_OFFTIME := T#2M,
    RUN_EVERY := T#10000M,
    RUNTIME := HK_Runtime,
    CYCLES := HK_Cycles
);

(* Invertierte Relais-Logik *)
IF xSetpoints[15] < INT#0 THEN
    O2_UmwaelzHK1 := NOT FALSE;
ELSIF xSetpoints[15] > INT#0 THEN
    O2_UmwaelzHK1 := NOT TRUE;
ELSE
    O2_UmwaelzHK1 := NOT ACTUATOR_HK.PUMP;
END_IF;
(* ========================================================================== *)
(* 5.3 BRUNNENPUMPE - LÄUFT IMMER (außer Force OFF)                         *)
(* ========================================================================== *)
bBR_Reason := BR_REASON_HK_ACTIVE;  (* Immer gesetzt = läuft immer *)

(* Override-Handling *)
IF xSetpoints[16] < INT#0 THEN
    (* Force OFF *)
    O3_Brunnen := FALSE;
    bBR_Reason := BYTE#0;
ELSIF xSetpoints[16] > INT#0 THEN
    (* Force ON *)
    O3_Brunnen := TRUE;
    bBR_Reason := BYTE#4;
ELSE
    (* Auto = IMMER AN *)
    O3_Brunnen := TRUE;
END_IF;

(* ACTUATOR nur für Runtime-Tracking *)
ACTUATOR_BR(
    IN := O3_Brunnen,
    MANUAL := FALSE,
    RST := FALSE,
    MIN_ONTIME := T#1S,
    MIN_OFFTIME := T#1S,
    RUN_EVERY := T#10000M,
    RUNTIME := BR_Runtime,
    CYCLES := BR_Cycles
);
(* ========================================================================== *)
(* 6. UPTIME & BETRIEBSSTUNDEN                                                *)
(* ========================================================================== *)
Timer_OneSecond(IN := TRUE, PT := T#1000ms);
IF Timer_OneSecond.Q THEN
    Timer_OneSecond(IN := FALSE);
    second_tick := TRUE;
    uptime_seconds := uptime_seconds + 1;
ELSE
    second_tick := FALSE;
END_IF;

(* ========================================================================== *)
(* 7. MODBUS MAPPING                                                          *)
(* ========================================================================== *)
status_word := INT#0;

(* Status-Word mit invertierten Pumpen *)
IF O1_WWPump = FALSE THEN status_word := status_word + INT#1; END_IF;
IF O2_UmwaelzHK1 = FALSE THEN status_word := status_word + INT#2; END_IF;
IF O3_Brunnen THEN status_word := status_word + INT#4; END_IF;
IF bNachtAbsenkung THEN status_word := status_word + INT#8; END_IF;
IF mux_state THEN status_word := status_word + INT#16; END_IF;
IF bDataReady THEN status_word := status_word + INT#32; END_IF;
IF bSensorError THEN status_word := status_word + INT#64; END_IF;

version_word := BYTE_TO_INT(VERSION_MAJOR) * INT#256 + BYTE_TO_INT(VERSION_MINOR);

QB0_shadow := %QB0;

(* xMeasure Array füllen *)
xMeasure[1]  := WORD_TO_INT(S_Vorlauf);
xMeasure[2]  := WORD_TO_INT(S_Aussen);
xMeasure[3]  := WORD_TO_INT(S_Innen);
xMeasure[4]  := WORD_TO_INT(S_Kessel);
xMeasure[5]  := WORD_TO_INT(S_Warmw);
xMeasure[6]  := WORD_TO_INT(S_Oeltank);
xMeasure[7]  := WORD_TO_INT(S_Ruecklauf);
xMeasure[8]  := WORD_TO_INT(S_Solar);
xMeasure[9]  := WORD_TO_INT(DI8chan);
xMeasure[10] := hour_of_day;
xMeasure[11] := status_word;

temp_var := REAL_TO_INT(temp_diff_ww * 100.0);
xMeasure[12] := temp_var;
temp_var := REAL_TO_INT(temp_kessel * 100.0);
xMeasure[13] := temp_var;
temp_var := REAL_TO_INT(temp_warmw * 100.0);
xMeasure[14] := temp_var;
temp_var := REAL_TO_INT(temp_vorlauf * 100.0);
xMeasure[15] := temp_var;

xMeasure[16] := version_word;
xMeasure[17] := BYTE_TO_INT(VERSION_PATCH);
xMeasure[18] := INT#15;

IF WW_Runtime < 32767 THEN
    xMeasure[19] := UDINT_TO_INT(WW_Runtime);
ELSE
    xMeasure[19] := 32767;
END_IF;

IF HK_Runtime < 32767 THEN
    xMeasure[20] := UDINT_TO_INT(HK_Runtime);
ELSE
    xMeasure[20] := 32767;
END_IF;

IF BR_Runtime < 32767 THEN
    xMeasure[21] := UDINT_TO_INT(BR_Runtime);
ELSE
    xMeasure[21] := 32767;
END_IF;

IF WW_Cycles < 32767 THEN
    xMeasure[22] := UDINT_TO_INT(WW_Cycles);
ELSE
    xMeasure[22] := 32767;
END_IF;

IF HK_Cycles < 32767 THEN
    xMeasure[23] := UDINT_TO_INT(HK_Cycles);
ELSE
    xMeasure[23] := 32767;
END_IF;

IF BR_Cycles < 32767 THEN
    xMeasure[24] := UDINT_TO_INT(BR_Cycles);
ELSE
    xMeasure[24] := 32767;
END_IF;

xMeasure[25] := BYTE_TO_INT(bWW_Reason);
xMeasure[26] := BYTE_TO_INT(bHK_Reason);
xMeasure[27] := BYTE_TO_INT(bBR_Reason);

temp_var := REAL_TO_INT(temp_aussen * 100.0);
xMeasure[28] := temp_var;
temp_var := REAL_TO_INT(temp_innen * 100.0);
xMeasure[29] := temp_var;
temp_var := REAL_TO_INT(temp_ruecklauf * 100.0);
xMeasure[30] := temp_var;
temp_var := REAL_TO_INT(temp_solar * 100.0);
xMeasure[31] := temp_var;

xMeasure[32] := BYTE_TO_INT(QB0_shadow);

(* xSystem Array füllen *)
xSystem[1] := UDINT_TO_INT(uptime_seconds MOD UDINT#65536);
xSystem[2] := UDINT_TO_INT(uptime_seconds / UDINT#65536);
xSystem[3] := error_counter;

(* xStats Array füllen *)
xStats[1] := UDINT_TO_INT(HK_Runtime / 3600);
xStats[2] := UDINT_TO_INT(WW_Runtime / 3600);
xStats[3] := UDINT_TO_INT(BR_Runtime / 3600);

IF HK_Cycles < 32767 THEN
    xStats[4] := UDINT_TO_INT(HK_Cycles);
ELSE
    xStats[4] := 32767;
END_IF;

IF WW_Cycles < 32767 THEN
    xStats[5] := UDINT_TO_INT(WW_Cycles);
ELSE
    xStats[5] := 32767;
END_IF;

IF BR_Cycles < 32767 THEN
    xStats[6] := UDINT_TO_INT(BR_Cycles);
ELSE
    xStats[6] := 32767;
END_IF;
