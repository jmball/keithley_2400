# Source and sense command coverage

`keithley2400` provides the Series 2400 source, measurement, output, and routing SCPI controls. Numeric settings accept numbers or documented SCPI numeric tokens such as `MIN`, `MAX`, and `DEF` where the command accepts them. Model-specific restrictions are left to instrument error reporting.

| Manual command header | Python API |
|---|---|
| `OUTPut:STATe` | `output_enabled` |
| `OUTPut:IENABle[:STATe]` | `output_enable` |
| `OUTPut:ENABle:TRIPped?` | `output_enable_tripped` |
| `OUTPut:SMODe` | `output_off_mode` |
| `ROUTe:TERMinals` | `terminals` |
| `SENSe:FUNCtion:CONCurrent` | `sense_concurrent` |
| `SENSe:FUNCtion[:ON]?` | `sense_functions` (read-only) |
| `SENSe:FUNCtion[:ON] <function list>` | `enable_sense_functions(functions)` |
| `SENSe:FUNCtion:ON:ALL` | `enable_all_sense_functions` |
| `SENSe:FUNCtion:ON:COUNt?` | `enabled_sense_function_count` |
| `SENSe:FUNCtion:OFF` | `disable_sense_functions` |
| `SENSe:FUNCtion:OFF:ALL` | `disable_all_sense_functions` |
| `SENSe:FUNCtion:OFF:COUNt?` | `disabled_sense_function_count` |
| `SENSe:FUNCtion:OFF?` | `disabled_sense_functions` |
| `SENSe:FUNCtion:STATe?` | `sense_function_enabled(function)` |
| `SENSe:CURRent:RANGe[:UPPer]` | `sense_current_range` |
| `SENSe:CURRent:RANGe:AUTO` | `sense_current_auto_range`; single-function alias `sense_auto_range` |
| `SENSe:CURRent:RANGe:AUTO:ULIMit?` | `sense_current_range_upper_limit` |
| `SENSe:CURRent:RANGe:AUTO:LLIMit` | `sense_current_range_lower_limit` |
| `SENSe:CURRent:NPLCycles` | `sense_current_nplc`; global alias `nplc` |
| `SENSe:CURRent:PROTection[:LEVel]` | `current_compliance` |
| `SENSe:CURRent:PROTection:TRIPped?` | `current_compliance_tripped` |
| `SENSe:CURRent:PROTection:RSYNchronize` | `current_range_synchronized` |
| `SENSe:VOLTage:RANGe[:UPPer]` | `sense_voltage_range` |
| `SENSe:VOLTage:RANGe:AUTO` | `sense_voltage_auto_range`; single-function alias `sense_auto_range` |
| `SENSe:VOLTage:RANGe:AUTO:ULIMit?` | `sense_voltage_range_upper_limit` |
| `SENSe:VOLTage:RANGe:AUTO:LLIMit` | `sense_voltage_range_lower_limit` |
| `SENSe:VOLTage:NPLCycles` | `sense_voltage_nplc`; global alias `nplc` |
| `SENSe:VOLTage:PROTection[:LEVel]` | `voltage_compliance` |
| `SENSe:VOLTage:PROTection:TRIPped?` | `voltage_compliance_tripped` |
| `SENSe:VOLTage:PROTection:RSYNchronize` | `voltage_range_synchronized` |
| `SENSe:RESistance:MODE` | `resistance_mode` |
| `SENSe:RESistance:OCOMpensated` | `offset_compensated_ohms` |
| `SENSe:RESistance:RANGe[:UPPer]` | `sense_resistance_range` |
| `SENSe:RESistance:RANGe:AUTO` | `sense_resistance_auto_range`; single-function alias `sense_auto_range` |
| `SENSe:RESistance:RANGe:AUTO:ULIMit` | `sense_resistance_range_upper_limit` |
| `SENSe:RESistance:RANGe:AUTO:LLIMit` | `sense_resistance_range_lower_limit` |
| `SENSe:CURRent:RANGe:HOLDoff` | `sense_current_range_holdoff` (source memory sweep feature) |
| `SENSe:CURRent:RANGe:HOLDoff:DELay` | `sense_current_range_holdoff_delay` |
| `SENSe:RESistance:NPLCycles` | `sense_resistance_nplc`; global alias `nplc` |
| `SENSe:AVERage:TCONtrol` | `average_type` |
| `SENSe:AVERage:COUNt` | `average_count` |
| `SENSe:AVERage[:STATe]` | `averaging_enabled` |
| `SOURce:CLEar[:IMMediate]` | `clear_source()` |
| `SOURce:CLEar:AUTO` | `auto_output_off` |
| `SOURce:CLEar:AUTO:MODE` | `auto_output_off_mode` |
| `SOURce:FUNCtion:SHAPe` (2430) | `pulse_shape` |
| `SOURce:FUNCtion[:MODE]` | `source_function` (`VOLT`, `CURR`, or documented `MEM`) |
| `SOURce:DELay` | `source_delay` |
| `SOURce:DELay:AUTO` | `source_delay_auto` |
| `SOURce:CURRent:MODE` | `source_current_mode` |
| `SOURce:CURRent:RANGe` | `source_current_range` |
| `SOURce:CURRent:RANGe:AUTO` | `source_current_auto_range` |
| `SOURce:CURRent[:LEVel][:IMMediate][:AMPLitude]` | `source_current_level`; aliases `source_level` when CURR selected |
| `SOURce:CURRent:LEVel:TRIGgered[:AMPLitude]` | `source_current_triggered_level` |
| `SOURce:CURRent:LEVel:TRIGgered:SFACtor` | `source_current_scaling_factor` |
| `SOURce:CURRent:LEVel:TRIGgered:SFACtor:STATe` | `source_current_scaling_enabled` |
| `SOURce:CURRent:STARt`, `STOP`, `STEP`, `CENTer`, `SPAN` | `source_current_start`, `source_current_stop`, `source_current_step`, `source_current_center`, `source_current_span` |
| `SOURce:VOLTage:MODE` | `source_voltage_mode` |
| `SOURce:VOLTage:RANGe` | `source_voltage_range` |
| `SOURce:VOLTage:RANGe:AUTO` | `source_voltage_auto_range` |
| `SOURce:VOLTage[:LEVel][:IMMediate][:AMPLitude]` | `source_voltage_level`; aliases `source_level` when VOLT selected |
| `SOURce:VOLTage:LEVel:TRIGgered[:AMPLitude]` | `source_voltage_triggered_level` |
| `SOURce:VOLTage:LEVel:TRIGgered:SFACtor` | `source_voltage_scaling_factor` |
| `SOURce:VOLTage:LEVel:TRIGgered:SFACtor:STATe` | `source_voltage_scaling_enabled` |
| `SOURce:VOLTage:PROTection[:LEVel]` | `voltage_protection` |
| `SOURce:VOLTage:PROTection:TRIPped?` | `voltage_protection_tripped` |
| `SOURce:VOLTage:STARt`, `STOP`, `STEP`, `CENTer`, `SPAN` | `source_voltage_start`, `source_voltage_stop`, `source_voltage_step`, `source_voltage_center`, `source_voltage_span` |
| `SOURce:SOAK` | `sweep_soak` |
| `SOURce:SWEep:SPACing` | `sweep_spacing` |
| `SOURce:SWEep:POINts` | `sweep_points` |
| `SOURce:SWEep:DIRection` | `sweep_direction` |
| `SOURce:SWEep:RANGing` | `sweep_ranging` |
| `SOURce:SWEep:CABort` | `sweep_compliance_abort` |
| `SOURce:LIST:CURRent` / `VOLTage` | `source_current_list_values`, `source_voltage_list_values` |
| `SOURce:LIST:CURRent:APPend` / `VOLTage:APPend` | `append_source_current_list(values)`, `append_source_voltage_list(values)` |
| `SOURce:LIST:CURRent:POINts?` / `VOLTage:POINts?` | `source_current_list_points`, `source_voltage_list_points` |
| `SOURce:LIST:CURRent:STARt` / `VOLTage:STARt` | `source_current_list_start`, `source_voltage_list_start` |
| `SOURce:MEMory:POINts` | `memory_points` |
| `SOURce:MEMory:STARt` | `memory_start` |
| `SOURce:MEMory:SAVE` | `save_memory(location)` |
| `SOURce:MEMory:RECall` | `recall_memory(location)` |
| `SOURce:PULSe:WIDTh`, `DELay` (2430) | `pulse_width`, `pulse_delay` |
| `SOURce2:BSIZe` | `digital_bit_size` |
| `SOURce2:TTL[:LEVel][:DEFault]` | `digital_output_pattern` |
| `SOURce2:TTL:LEVel:ACTual?` | `digital_output_actual` |
| `SOURce2:TTL4:MODE` | `digital_line4_mode` |
| `SOURce2:TTL4:BSTate` | `digital_busy_polarity` |
| `SOURce2:CLEar[:IMMediate]` | `clear_digital_output()` |
| `SOURce2:CLEar:AUTO` | `digital_clear_auto` |
| `SOURce2:CLEar:AUTO:DELay` | `digital_clear_delay` |

`sense_auto_range` infers the sole selected measurement function and raises `ValueError` when several are selected. Use `sense_voltage_auto_range`, `sense_current_auto_range`, or `sense_resistance_auto_range` for concurrent measurement setups. `nplc` is global and uses the documented voltage-path alias. `source_function` selects the source path only; `source_voltage_mode` and `source_current_mode` independently controls FIXed, SWEep, or LIST.

The output-enable trip query returns 1 when output is permitted and 0 when it is blocked (page 18-56). `output_enable_tripped` converts that inverted bit to the usual Python boolean meaning: `True` means output is blocked.

`sense_functions` only reads the enabled functions. Setting concurrency and replacing the enabled set is an application recipe shown in `examples/advanced_configuration.py`, using the individual driver operations.
