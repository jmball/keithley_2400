# Calculation, display, format, and status commands

This page maps the command headers in the Keithley 2400 Series User’s Manual,
Section 18 Tables 18-1 through 18-3 and 18-8, to `CalculationCommands`. SCPI
headers below use manual spelling; the Python API sends documented short forms.
`data_format` and `byte_order` belong to the main driver because its reading
protocol owns binary parsing.

## CALCulate[1]

| Documented command | Python API |
| --- | --- |
| `:CALCulate[1]:MATH[:EXPRession] <form>` / `:MATH?` | `math.expression` |
| `:CALCulate[1]:MATH:CATalog?` | `math.catalog` |
| `:CALCulate[1]:MATH:NAME <name>` / `?` | `math.name` |
| `:CALCulate[1]:MATH[:DEFine] <form>` | `math.expression` setter (canonical `EXPRession`) |
| `:CALCulate[1]:MATH:DELete[:SEL] <name>` | `math.delete(name)` |
| `:CALCulate[1]:MATH:DELete:ALL` | `math.delete_all()` |
| `:CALCulate[1]:MATH:UNITs <name>` / `?` | `math.units` |
| `:CALCulate[1]:STATe <b>` / `?` | `math.enabled` |
| `:CALCulate[1]:DATA?` | `math.data` |
| `:CALCulate[1]:DATA:LATest?` | `math.latest` |

The built-in math names (POWER, OFFCOMPOHM, VOLTCOEF, VARALPHA, and `%DEV`)
and the user-expression grammar are supplied unchanged to the instrument. `%DEV`
is listed in the catalog but available only from the front panel. The manual
allows up to 10 ASCII characters for a custom name, three characters for units,
and the functions VOLTage, CURRent, RESistance, TIME with `+ - * / ^ log ln
sin cos tan exp` operators.

## CALCulate2

| Documented command | Python API |
| --- | --- |
| `:CALCulate2:FEED <name>` / `?` | `limit_feed` |
| `:CALCulate2:NULL:OFFSet <NRf>` / `?` | `relative.offset` |
| `:CALCulate2:NULL:STATe <b>` / `?` | `relative.enabled` |
| `:CALCulate2:NULL:ACQuire` | `relative.acquire()` |
| `:CALCulate2:DATA?` / `:DATA:LATest?` | `limit_data`, `limit_latest` |
| `:CALCulate2:LIMit[1]:COMPliance:FAIL <name>` / `?` | `limit(1).compliance_fail_condition` |
| `:CALCulate2:LIMit[1]:COMPliance:SOURce2 <NRf\|NDN>` / `?` | `limit(1).fail_pattern` |
| `:CALCulate2:LIMit[1]:STATe <b>` / `?`; `:FAIL?` | `limit(1).enabled`; `limit(1).failed` |
| `:CALCulate2:LIMit2,3,5…12:UPPer[:DATA] <n>` / `?` | `limit(index).upper` |
| `:CALCulate2:LIMit2,3,5…12:LOWer[:DATA] <n>` / `?` | `limit(index).lower` |
| `:CALCulate2:LIMit2,3,5…12:UPPer:SOURce2 <NRf\|NDN>` / `?` | `limit(index).upper_fail_pattern` |
| `:CALCulate2:LIMit2,3,5…12:LOWer:SOURce2 <NRf\|NDN>` / `?` | `limit(index).fail_pattern` |
| `:CALCulate2:LIMit2,3,5…12:PASS:SOURce2 <NRf\|NDN>` / `?` | `limit(index).pass_pattern` |
| `:CALCulate2:LIMit2,3,4,5…12:STATe <b>` / `?`; `:FAIL?` | `limit(index).enabled`; `limit(index).failed` |
| `:CALCulate2:LIMit4:SOURce2 <NRf\|NDN>` / `?` | `limit(4).fail_pattern` |
| `:CALCulate2:CLIMits:PASS:SOURce2 <NRf\|NDN>` / `?`; summary Table 18-1 p18-7: `:CALCulate2:PASS:SOURce2` | `composite_limits.pass_pattern` |
| `:CALCulate2:CLIMits:FAIL:SOURce2 <NRf\|NDN>` / `?`; summary Table 18-1 p18-7: `:CALCulate2:FAIL:SOURce2` | `composite_limits.fail_pattern` |
| `:CALCulate2:CLIMits:PASS:SMLocation <NRf\|NEXT>` / `?` | `composite_limits.pass_memory_location` |
| `:CALCulate2:CLIMits:FAIL:SMLocation <NRf\|NEXT>` / `?` | `composite_limits.fail_memory_location` |
| `:CALCulate2:CLIMits:MODE <name>` / `?` | `composite_limits.mode` |
| `:CALCulate2:CLIMits:BCONtrol <name>` / `?` | `composite_limits.bin_control` |
| `:CALCulate2:CLEar[:IMMediate]` | `composite_limits.clear()` |
| `:CALCulate2:CLEar:AUTO <b>` / `?` | `composite_limits.auto_clear` |

Limits 2, 3, and 5 through 12 expose numeric thresholds as documented;
Limit 4 is the contact-check test and has a bit pattern and state/result but no
numeric thresholds. Appendix F requires remote sensing to be enabled for
contact check. Reading a limit failure does not clear its failure indication;
the manual says to clear it with `:SYSTem:CLEar`. Limit 4 availability depends
on the contact-check option. Digital output patterns are sent as supplied; the
instrument interprets them as NRf or NDN and their width depends on the
instrument's 3-bit/4-bit Digital I/O configuration. Limit indexes 1–12 map to
the physical SCPI limit number. Table 18-1 p18-7 presents composite PASS and
FAIL fields as siblings of CLEar under CALCulate2; detailed command descriptions
on p18-39–42 give them under CLIMits, which is the command path used here.

## CALCulate3 and DISPlay

| Documented command | Python API |
| --- | --- |
| `:CALCulate3:FORMat <name>` / `?` | `calc3.statistic` |
| `:CALCulate3:DATA?` | `calc3.data` |
| `:DISPlay:ENABle <b>` / `?` | `display_enabled` |
| `:DISPlay:CNDisplay` | `display_source_measure()` |
| `:DISPlay[:WINDow[1]]:TEXT:DATA <a>` / `?` | `display_top.text` |
| `:DISPlay[:WINDow[1]]:TEXT:STATe <b>` / `?` | `display_top.text_enabled` |
| `:DISPlay[:WINDow[1]]:DATA?` | `display_top.data` |
| `:DISPlay[:WINDow[1]]:ATTRibutes?` | `display_top.attributes` |
| `:DISPlay:WINDow2:TEXT:DATA <a>` / `?` | `display_bottom.text` |
| `:DISPlay:WINDow2:TEXT:STATe <b>` / `?` | `display_bottom.text_enabled` |
| `:DISPlay:WINDow2:DATA?` | `display_bottom.data` |
| `:DISPlay:WINDow2:ATTRibutes?` | `display_bottom.attributes` |
| `:DISPlay:DIGits <n>` / `?` | `display_digits` |

CALC3 supports MEAN, SDEViation, MAXimum, MINimum, and PKPK. The display
accepts 4–7 digits. User messages are up to 20 characters on the top line and
32 on the bottom line. Display and user-message reset behavior follows the
notes in Table 18-2: reset/preset do not clear the display circuit, text, or
message-mode state; LOCAL or power cycling affects them as described there.

## FORMat (excluding DATA and BORDer)

| Documented command | Python API |
| --- | --- |
| `:FORMat:SREGister <name>` / `?` | `status_register_format` |
| `:FORMat:ELEMents [SENSe[1]] <item list>` / `:ELEMents?` | `data_elements` |
| `:FORMat:ELEMents:CALCulate <item list>` / `?` | `calculation_elements` |
| `:FORMat:SOURce2 <name>` / `?` | `digital_format` |

The main driver supplies `data_format` for `:FORMat[:DATA]` and `byte_order`
for `:FORMat:BORDer`. Status-register output formats are ASCII, HEX, OCT, or
BIN; digital output formats are ASCII, HEX, OCT, or BIN. Element lists accept
VOLTage, CURRent, RESistance, TIME, STATus and CALC, TIME, STATus respectively.

## STATus

| Documented command | Python API |
| --- | --- |
| `:STATus:MEASurement:ENABle <mask>` / `?` | `measurement_status.enable` |
| `:STATus:MEASurement:CONDition?` | `measurement_status.condition` |
| `:STATus:MEASurement[:EVENt]?` | `measurement_status.read_event()` |
| `:STATus:OPERation:ENABle <mask>` / `?` | `operation_status.enable` |
| `:STATus:OPERation:CONDition?` | `operation_status.condition` |
| `:STATus:OPERation[:EVENt]?` | `operation_status.read_event()` |
| `:STATus:QUEStionable:ENABle <mask>` / `?` | `questionable_status.enable` |
| `:STATus:QUEStionable:CONDition?` | `questionable_status.condition` |
| `:STATus:QUEStionable[:EVENt]?` | `questionable_status.read_event()` |
| `:STATus:PRESet` | `preset_status()` |
| `:STATus:QUEue:ENABle <list>` / `?` | `error_queue_enabled` |
| `:STATus:QUEue:DISable <list>` / `?` | `error_queue_disabled` |
| `:STATus:QUEue[:NEXT]?` | `read_status_error()` |
| `:STATus:QUEue:CLEar` | `clear_status_errors()` |

Event-register reads clear the event bits they return. `STATus:PRESet` resets
enable registers but has no effect on event registers or the error queue. The
status group enable properties accept integer masks and read integer responses;
the communication layer parses SCPI non-decimal response forms. Error queue
enable/disable lists are passed through as comma-separated codes. CALC2 limit
failure-result reads report the current result without clearing its failure
indication.
