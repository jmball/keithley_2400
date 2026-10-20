# System, trace, trigger, and common commands

This page maps the Keithley 2400 User’s Manual commands in IEEE-488.2 Table 16-1,
signal-oriented Table 17-1, and subsystem Tables 18-8 through 18-11 to the
low-level Python API. These calls preserve the instrument’s format-dependent
reading data as a flat tuple of floats. `read()`, `fetch()`, `measure()`, and
`trace_data` use the shared `:FORM:DATA?` aware transfer helper.

## IEEE-488.2 common commands (Table 16-1)

| Instrument command | Python API | Notes |
|---|---|---|
| `*CLS` | `clear_status()` | Clears status event registers and the error queue. |
| `*ESE`, `*ESE?` | `event_status_enable` | Standard Event Status Enable register. |
| `*ESR?` | `read_event_status()` | Read and clear. |
| `*IDN?` | `identity` | Read-only instrument identity. |
| `*OPC` | `set_operation_complete()` | Queues completion-bit setting. |
| `*OPC?` | `wait_complete()` | Blocks for completion and returns whether the reply was `1`. |
| `*OPT?` | `options` | Installed option names. |
| `*RCL <NRf>` | `recall_setup(location)` | Location 0–4. |
| `*RST` | `reset()` | Restore *RST defaults. |
| `*SAV <NRf>` | `save_setup(location)` | Location 0–4. |
| `*SRE`, `*SRE?` | `service_request_enable` | Service Request Enable register. |
| `*STB?` | `status_byte` | Read Status Byte Register. |
| `*TRG` | `trigger_bus()` | Send bus trigger. |
| `*TST?` | `self_test()` | Runs the ROM checksum test. |
| `*WAI` | `wait_to_continue()` | Wait-to-continue command. |

Status register commands in Section 15 and Table 18-8 are mapped in the
calculation command reference. `read_error()` and `check_errors()` are supplied
by the shared communication base. The additional system error queue variants
are `read_errors()` (`:SYST:ERR:ALL?`), `error_count`, `read_error_code()`,
`read_error_codes()`, and `clear_errors()`.

## Signal-oriented measurement commands (Table 17-1)

| Instrument command | Python API | Notes |
|---|---|---|
| `:CONFigure:<function>` | `configure_measurement(function)` | Function accepts VOLT, CURR, or RES. This action changes instrument setup and turns the output on, as documented. |
| `:CONFigure?` | `configured_measurement` | Active function list. |
| `:FETCh?` | `fetch()` | Retrieves latest sample-buffer readings without initiating. |
| `:READ?` | `read()` | Initiates and then fetches readings. |
| `:MEASure[:<function>]?` | `measure(function=None)` | One-shot measurement; optional VOLT, CURR, or RES. |
| `[:SENSe[1]]:DATA[:LATest]?` | `sense_data_latest` | Latest reading values. |

## SYSTem subsystem (Table 18-9)

| Instrument command | Python API | Notes |
|---|---|---|
| `:SYSTem:PRESet` | `preset()` | Restore front-panel defaults. |
| `:SYSTem:POSetup`, `:SYSTem:POSetup?` | `power_on_setup` | Values RST, PRESet, SAV 0–4. |
| `:SYSTem:CCHeck`, `:SYSTem:CCHeck?` | `contact_check_enabled` | Contact check requires remote sensing. |
| `:SYSTem:CCHeck:RESistance`, query | `contact_check_resistance` | Threshold setting, 0–60 Ω. |
| `:SYSTem:RSENse`, query | `remote_sense` | Four-wire remote sensing. |
| `:SYSTem:GUARd`, query | `guard_mode` | OHMS or CABLE. |
| `:SYSTem:MEMory:INITialize` | `initialize_memory()` | Destructive to stored trace and setup data. |
| `:SYSTem:BEEPer[:IMMediate] <freq>,<time>` | `beep(frequency, duration)` | Immediate beep; beeper must be enabled. |
| `:SYSTem:BEEPer:STATe`, query | `beeper_enabled` | Enable front-panel beep feedback. |
| `:SYSTem:AZERo:STATe`, query | `auto_zero` | ON, OFF, or ONCE. ONCE performs an immediate update. |
| `:SYSTem:AZERo:CACHing[:STATe]`, query | `nplc_caching` | NPLC cache enable. |
| `:SYSTem:AZERo:CACHing:REFResh` | `refresh_nplc_cache()` | Refresh cached values. |
| `:SYSTem:AZERo:CACHing:RESet` | `reset_nplc_cache()` | Clear cached values. |
| `:SYSTem:AZERo:CACHing:NPLCycles?` | `cached_nplc_values` | Cached NPLC list. |
| `:SYSTem:LFRequency`, query | `line_frequency` | Select 50 or 60 Hz; 50 is used for 400 Hz mains. |
| `:SYSTem:LFRequency:AUTO`, query | `auto_line_frequency` | Automatic power-up detection. |
| `:SYSTem:ERRor[:NEXT]?` | `read_error()` | Shared communication base method; pops oldest error. |
| `:SYSTem:ERRor:ALL?` | `read_errors()` | Returns and removes all queued error strings. |
| `:SYSTem:ERRor:COUNt?` | `error_count` | Current queue length. |
| `:SYSTem:ERRor:CODE[:NEXT]?` | `read_error_code()` | Pops oldest code. |
| `:SYSTem:ERRor:CODE:ALL?` | `read_error_codes()` | Returns and removes queued codes. |
| `:SYSTem:CLEar` | `clear_errors()` | Clear error queue. |
| `:SYSTem:KEY`, `:SYSTem:KEY?` | `press_key(code)`, `read_last_key()` | Simulate/read documented key code. |
| `:SYSTem:VERSion?` | `scpi_version` | SCPI version string. |
| `:SYSTem:LOCal` | `local()` | Manual specifies RS-232 only. |
| `:SYSTem:RWLock`, query | `remote_lockout` | Manual specifies RS-232 only. |
| `:SYSTem:TIME?` | `timestamp` | Read current timestamp. |
| `:SYSTem:TIME:RESet` | `reset_timestamp()` | Reset timestamp to zero. |
| `:SYSTem:TIME:RESet:AUTO`, query | `auto_reset_timestamp` | Reset at exit from idle. |
| `:SYSTem:RCMode`, query | `range_change_mode` | SINGle or MULTiple. |

## TRACe subsystem (Table 18-10)

`:DATA` is a documented alias root for this subsystem; the driver uses `:TRACe`.

| Instrument command | Python API | Notes |
|---|---|---|
| `:TRACe:DATA?` | `trace_data` | Reads the contents of the buffer. |
| `:TRACe:CLEar` | `clear_trace()` | Clears stored readings. |
| `:TRACe:FREE?` | `trace_memory` | Returns available and reserved bytes. |
| `:TRACe:POINts`, query | `trace_points` | Buffer size, 1–2500. |
| `:TRACe:POINts? MINimum/MAXimum/DEFault` | `trace_points_limits` | Instrument-reported limits/default. |
| `:TRACe:POINts:ACTual?` | `trace_points_actual` | Number of stored reading arrays. |
| `:TRACe:FEED`, query | `trace_feed` | SENSe[1], CALCulate[1], or CALCulate2. |
| `:TRACe:FEED:CONTrol`, query | `trace_control` | NEXT or NEVer. |
| `:TRACe:TSTamp:FORMat`, query | `trace_timestamp_format` | ABSolute or DELTa. |

## TRIGger subsystem (Table 18-11)

| Instrument command | Python API | Notes |
|---|---|---|
| `:TRIGger:CLEar` | `clear_triggers()` | Clear pending input triggers. |
| `:INITiate[:IMMediate]` | `initiate()` | Start source-measure operation. |
| `:ABORt` | `abort()` | Abort and return to idle. |
| `:ARM:COUNt`, query | `arm_count` | Integer 1–2500 or `"INFINITE"`. |
| `:TRIGger:COUNt`, query | `trigger_count` | Integer 1–2500. |
| `:TRIGger:DELay`, query | `trigger_delay` | 0–999.9999 seconds. |
| `:ARM:SOURce`, query | `arm_source` | Arm event source. |
| `:TRIGger:SOURce`, query | `trigger_source` | Trigger-layer source is IMMediate or TLINk. |
| `:ARM:TIMer`, query | `arm_timer` | Arm timer period in seconds. |
| `:ARM:DIRection`, query | `arm_bypass` | SOURce or ACCeptor bypass behavior. |
| `:TRIGger:DIRection`, query | `trigger_bypass` | SOURce or ACCeptor bypass behavior. |
| `:ARM:ILINe`, `:TRIGger:ILINe` and queries | `arm_input_line`, `trigger_input_line` | Trigger Link input lines 1–4. |
| `:ARM:OLINe`, `:TRIGger:OLINe` and queries | `arm_output_line`, `trigger_output_line` | Trigger Link output lines 1–4. |
| `:ARM:OUTPut`, query | `arm_output_events` | TENTer, TEXit, or NONE. |
| `:TRIGger:OUTPut`, query | `trigger_output_events` | SOURce, DELay, SENSe, or NONE events. |
| `:TRIGger:INPut`, query | `trigger_input_events` | Enable source, delay, or sense detectors; NONE alone disables. |

The manual says the product of arm count and trigger count cannot exceed 2500;
the independent properties validate each count’s documented range but leave
the combined trigger-model constraint to the instrument. `ARM:COUNt INFinite`
has the instrument’s documented restrictions on fetch/read/measure operations.

## Appendix F contact-check and Appendix G protocol commands

| Instrument command | Python API | Notes |
|---|---|---|
| `:TRIGger:SEQuence2:SOURce`, query | `contact_check_event_source` | CCHeck enables event detection; IMMediate disables it. Contact-check option required. |
| `:TRIGger:SEQuence2:TOUT`, query | `contact_check_timeout` | Timeout in seconds, 0–999.99990. |
| `:SYSTem:MEP[:STATe]?` | `scpi_protocol_enabled` | 1 means SCPI protocol; 0 means 488.1 protocol. |
| `:SYSTem:MEP:HOLDoff ON\|OFF` | `set_mep_holdoff(enabled)` | Appendix G NDAC holdoff control. There is no documented query for this setting. |

Calibration service commands are outside the user manual command reference and
are not included. Appendix G describes 488.1 bus behavior in prose; this API
exposes the documented MEP state and holdoff SCPI commands only.

The detailed key-code reference on pages 18-110–111 includes key 32 (FRONT/REAR), although Table 18-9 lists 1–31. The driver follows the detailed reference.
