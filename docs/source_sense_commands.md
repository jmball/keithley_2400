# Source and sense command coverage

`SourceSenseCommands` provides the Series 2400 source, measurement, output, and routing SCPI controls. Numeric settings accept numbers or documented SCPI numeric tokens such as `MIN`, `MAX`, and `DEF` where the command accepts them. Model-specific restrictions are left to instrument error reporting.

| Manual command header | Python API |
|---|---|
| `OUTPut:STATe` | `output_enabled` |
| `OUTPut:IENABle[:STATe]` | `output_enable` |
| `OUTPut:ENABle:TRIPped?` | `output_enable_tripped` |
| `OUTPut:SMODe` | `output_off_mode` |
| `ROUTe:TERMinals` | `terminals` |
| `SENSe:FUNCtion:CONCurrent` | `sense_concurrent` |
| `SENSe:FUNCtion[:ON]` | `sense_functions`; `enable_sense_functions` |
| `SENSe:FUNCtion:ON:ALL` | `enable_all_sense_functions` |
| `SENSe:FUNCtion:ON:COUNt?` | `enabled_sense_function_count` |
| `SENSe:FUNCtion:OFF` | `disable_sense_functions` |
| `SENSe:FUNCtion:OFF:ALL` | `disable_all_sense_functions` |
| `SENSe:FUNCtion:OFF:COUNt?` | `disabled_sense_function_count` |
| `SENSe:FUNCtion:OFF?` | `disabled_sense_functions` |
| `SENSe:FUNCtion:STATe?` | `sense_function_enabled(function)` |
| `SENSe:CURRent:RANGe[:UPPer]` | `sense_current.range` |
| `SENSe:CURRent:RANGe:AUTO` | `sense_current.auto_range`; single-function alias `sense_auto_range` |
| `SENSe:CURRent:RANGe:AUTO:ULIMit?` | `sense_current.range_upper_limit` |
| `SENSe:CURRent:RANGe:AUTO:LLIMit` | `sense_current.range_lower_limit` |
| `SENSe:CURRent:NPLCycles` | `sense_current.nplc`; global alias `nplc` |
| `SENSe:CURRent:PROTection[:LEVel]` | `current_compliance` |
| `SENSe:CURRent:PROTection:TRIPped?` | `current_compliance_tripped` |
| `SENSe:CURRent:PROTection:RSYNchronize` | `current_range_synchronized` |
| `SENSe:VOLTage:RANGe[:UPPer]` | `sense_voltage.range` |
| `SENSe:VOLTage:RANGe:AUTO` | `sense_voltage.auto_range`; single-function alias `sense_auto_range` |
| `SENSe:VOLTage:RANGe:AUTO:ULIMit?` | `sense_voltage.range_upper_limit` |
| `SENSe:VOLTage:RANGe:AUTO:LLIMit` | `sense_voltage.range_lower_limit` |
| `SENSe:VOLTage:NPLCycles` | `sense_voltage.nplc`; global alias `nplc` |
| `SENSe:VOLTage:PROTection[:LEVel]` | `voltage_compliance` |
| `SENSe:VOLTage:PROTection:TRIPped?` | `voltage_compliance_tripped` |
| `SENSe:VOLTage:PROTection:RSYNchronize` | `voltage_range_synchronized` |
| `SENSe:RESistance:MODE` | `resistance_mode` |
| `SENSe:RESistance:OCOMpensated` | `offset_compensated_ohms` |
| `SENSe:RESistance:RANGe[:UPPer]` | `sense_resistance.range` |
| `SENSe:RESistance:RANGe:AUTO` | `sense_resistance.auto_range`; single-function alias `sense_auto_range` |
| `SENSe:RESistance:RANGe:AUTO:ULIMit` | `sense_resistance.range_upper_limit` |
| `SENSe:RESistance:RANGe:AUTO:LLIMit` | `sense_resistance.range_lower_limit` |
| `SENSe:CURRent:RANGe:HOLDoff` | `sense_current.range_holdoff` (source memory sweep feature) |
| `SENSe:CURRent:RANGe:HOLDoff:DELay` | `sense_current.range_holdoff_delay` |
| `SENSe:RESistance:NPLCycles` | `sense_resistance.nplc`; global alias `nplc` |
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
| `SOURce:CURRent:MODE` | `source_current.mode` |
| `SOURce:CURRent:RANGe` | `source_current.range` |
| `SOURce:CURRent:RANGe:AUTO` | `source_current.auto_range` |
| `SOURce:CURRent[:LEVel][:IMMediate][:AMPLitude]` | `source_current.level`; aliases `source_level` when CURR selected |
| `SOURce:CURRent:LEVel:TRIGgered[:AMPLitude]` | `source_current.triggered_level` |
| `SOURce:CURRent:LEVel:TRIGgered:SFACtor` | `source_current.scaling_factor` |
| `SOURce:CURRent:LEVel:TRIGgered:SFACtor:STATe` | `source_current.scaling_enabled` |
| `SOURce:CURRent:STARt`, `STOP`, `STEP`, `CENTer`, `SPAN` | matching `source_current` properties |
| `SOURce:VOLTage:MODE` | `source_voltage.mode` |
| `SOURce:VOLTage:RANGe` | `source_voltage.range` |
| `SOURce:VOLTage:RANGe:AUTO` | `source_voltage.auto_range` |
| `SOURce:VOLTage[:LEVel][:IMMediate][:AMPLitude]` | `source_voltage.level`; aliases `source_level` when VOLT selected |
| `SOURce:VOLTage:LEVel:TRIGgered[:AMPLitude]` | `source_voltage.triggered_level` |
| `SOURce:VOLTage:LEVel:TRIGgered:SFACtor` | `source_voltage.scaling_factor` |
| `SOURce:VOLTage:LEVel:TRIGgered:SFACtor:STATe` | `source_voltage.scaling_enabled` |
| `SOURce:VOLTage:PROTection[:LEVel]` | `voltage_protection` |
| `SOURce:VOLTage:PROTection:TRIPped?` | `voltage_protection_tripped` |
| `SOURce:VOLTage:STARt`, `STOP`, `STEP`, `CENTer`, `SPAN` | matching `source_voltage` properties |
| `SOURce:SOAK` | `sweep_soak` |
| `SOURce:SWEep:SPACing` | `sweep_spacing` |
| `SOURce:SWEep:POINts` | `sweep_points` |
| `SOURce:SWEep:DIRection` | `sweep_direction` |
| `SOURce:SWEep:RANGing` | `sweep_ranging` |
| `SOURce:SWEep:CABort` | `sweep_compliance_abort` |
| `SOURce:LIST:CURRent` / `VOLTage` | `source_current.list_values`, `source_voltage.list_values` |
| `SOURce:LIST:CURRent:APPend` / `VOLTage:APPend` | `source_current.append_list(values)`, `source_voltage.append_list(values)` |
| `SOURce:LIST:CURRent:POINts?` / `VOLTage:POINts?` | `source_current.list_points`, `source_voltage.list_points` |
| `SOURce:LIST:CURRent:STARt` / `VOLTage:STARt` | `source_current.list_start`, `source_voltage.list_start` |
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

`sense_auto_range` infers the sole selected measurement function and raises `ValueError` when several are selected. Use the explicit `sense_voltage`, `sense_current`, or `sense_resistance` endpoint for concurrent measurement setups. `nplc` is global and uses the documented voltage-path alias. `source_function` selects the source path only; each channel's `.mode` independently controls FIXed, SWEep, or LIST.

The output-enable trip query returns 1 when output is permitted and 0 when it is blocked (page 18-56). `output_enable_tripped` converts that inverted bit to the usual Python boolean meaning: `True` means output is blocked.
