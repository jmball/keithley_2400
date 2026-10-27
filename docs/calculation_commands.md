# Calculation, display, format, and status commands

This page maps the command headers in the Keithley 2400 Series User’s Manual,
Section 18 Tables 18-1 through 18-3 and 18-8, to direct members on `keithley2400`. SCPI
headers below use manual spelling; the Python API sends documented short forms.
`data_format` and `byte_order` belong to the main driver because its reading
protocol owns binary parsing.

## CALCulate[1]

| Documented command | Python API |
| --- | --- |
| `:CALCulate[1]:MATH[:EXPRession] <form>` / `:MATH?` | `math_expression` |
| `:CALCulate[1]:MATH:CATalog?` | `math_catalog` |
| `:CALCulate[1]:MATH:NAME <name>` / `?` | `math_name` |
| `:CALCulate[1]:MATH[:DEFine] <form>` | `math_expression` setter (canonical `EXPRession`) |
| `:CALCulate[1]:MATH:DELete[:SEL] <name>` | `delete_math_expression(name)` |
| `:CALCulate[1]:MATH:DELete:ALL` | `delete_all_math_expressions()` |
| `:CALCulate[1]:MATH:UNITs <name>` / `?` | `math_units` |
| `:CALCulate[1]:STATe <b>` / `?` | `math_enabled` |
| `:CALCulate[1]:DATA?` | `math_data` |
| `:CALCulate[1]:DATA:LATest?` | `math_latest` |

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
| `:CALCulate2:NULL:OFFSet <NRf>` / `?` | `relative_offset` |
| `:CALCulate2:NULL:STATe <b>` / `?` | `relative_enabled` |
| `:CALCulate2:NULL:ACQuire` | `acquire_relative()` |
| `:CALCulate2:DATA?` / `:DATA:LATest?` | `limit_data`, `limit_latest` |
| `:CALCulate2:LIMit[1]:COMPliance:FAIL <name>` / `?` | `limit_test_1_compliance_fail_condition` |
| `:CALCulate2:LIMit[1]:COMPliance:SOURce2 <NRf\|NDN>` / `?` | `get_limit_test_fail_pattern(1)`, `set_limit_test_fail_pattern(1, value)` |
| `:CALCulate2:LIMit[1]:STATe <b>` / `?`; `:FAIL?` | `get_limit_test_enabled(1)`, `set_limit_test_enabled(1, value)`; `get_limit_test_failed(1)` |
| `:CALCulate2:LIMit2,3,5…12:UPPer[:DATA] <n>` / `?` | `get_limit_test_upper(index)`, `set_limit_test_upper(index, value)` |
| `:CALCulate2:LIMit2,3,5…12:LOWer[:DATA] <n>` / `?` | `get_limit_test_lower(index)`, `set_limit_test_lower(index, value)` |
| `:CALCulate2:LIMit2,3,5…12:UPPer:SOURce2 <NRf\|NDN>` / `?` | `get_limit_test_upper_fail_pattern(index)`, `set_limit_test_upper_fail_pattern(index, value)` |
| `:CALCulate2:LIMit2,3,5…12:LOWer:SOURce2 <NRf\|NDN>` / `?` | `get_limit_test_fail_pattern(index)`, `set_limit_test_fail_pattern(index, value)` |
| `:CALCulate2:LIMit2,3,5…12:PASS:SOURce2 <NRf\|NDN>` / `?` | `get_limit_test_pass_pattern(index)`, `set_limit_test_pass_pattern(index, value)` |
| `:CALCulate2:LIMit2,3,4,5…12:STATe <b>` / `?`; `:FAIL?` | `get_limit_test_enabled(index)`, `set_limit_test_enabled(index, value)`; `get_limit_test_failed(index)` |
| `:CALCulate2:LIMit4:SOURce2 <NRf\|NDN>` / `?` | `get_limit_test_fail_pattern(4)`, `set_limit_test_fail_pattern(4, value)` |
| `:CALCulate2:CLIMits:PASS:SOURce2 <NRf\|NDN>` / `?`; summary Table 18-1 p18-7: `:CALCulate2:PASS:SOURce2` | `composite_limit_pass_pattern` |
| `:CALCulate2:CLIMits:FAIL:SOURce2 <NRf\|NDN>` / `?`; summary Table 18-1 p18-7: `:CALCulate2:FAIL:SOURce2` | `composite_limit_fail_pattern` |
| `:CALCulate2:CLIMits:PASS:SMLocation <NRf\|NEXT>` / `?` | `composite_limit_pass_memory_location` |
| `:CALCulate2:CLIMits:FAIL:SMLocation <NRf\|NEXT>` / `?` | `composite_limit_fail_memory_location` |
| `:CALCulate2:CLIMits:MODE <name>` / `?` | `composite_limit_mode` |
| `:CALCulate2:CLIMits:BCONtrol <name>` / `?` | `composite_limit_bin_control` |
| `:CALCulate2:CLEar[:IMMediate]` | `clear_composite_limits()` |
| `:CALCulate2:CLEar:AUTO <b>` / `?` | `composite_limit_auto_clear` |

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
| `:CALCulate3:FORMat <name>` / `?` | `statistics_function` |
| `:CALCulate3:DATA?` | `statistics_data` |
| `:DISPlay:ENABle <b>` / `?` | `display_enabled` |
| `:DISPlay:CNDisplay` | `display_source_measure()` |
| `:DISPlay[:WINDow[1]]:TEXT:DATA <a>` / `?` | `display_top_text` |
| `:DISPlay[:WINDow[1]]:TEXT:STATe <b>` / `?` | `display_top_text_enabled` |
| `:DISPlay[:WINDow[1]]:DATA?` | `display_top_data` |
| `:DISPlay[:WINDow[1]]:ATTRibutes?` | `display_top_attributes` |
| `:DISPlay:WINDow2:TEXT:DATA <a>` / `?` | `display_bottom_text` |
| `:DISPlay:WINDow2:TEXT:STATe <b>` / `?` | `display_bottom_text_enabled` |
| `:DISPlay:WINDow2:DATA?` | `display_bottom_data` |
| `:DISPlay:WINDow2:ATTRibutes?` | `display_bottom_attributes` |
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
| `:STATus:MEASurement:ENABle <mask>` / `?` | `measurement_status_enable` |
| `:STATus:MEASurement:CONDition?` | `measurement_status_condition` |
| `:STATus:MEASurement[:EVENt]?` | `read_measurement_status_event()` |
| `:STATus:OPERation:ENABle <mask>` / `?` | `operation_status_enable` |
| `:STATus:OPERation:CONDition?` | `operation_status_condition` |
| `:STATus:OPERation[:EVENt]?` | `read_operation_status_event()` |
| `:STATus:QUEStionable:ENABle <mask>` / `?` | `questionable_status_enable` |
| `:STATus:QUEStionable:CONDition?` | `questionable_status_condition` |
| `:STATus:QUEStionable[:EVENt]?` | `read_questionable_status_event()` |
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

The numbered `limit_test` methods address measurement pass/fail tests in
`CALCulate2:LIMit<n>`, rather than source compliance settings or measurement
ranges. Test 1 checks compliance, test 4 checks contact, and tests 2, 3, and
5–12 compare measurements with lower and upper thresholds. Digital patterns
specify the test's pass/fail outputs. For numeric tests, `get_limit_test_fail_pattern`
and `set_limit_test_fail_pattern` address the lower-threshold failure pattern.
