# Command coverage

Source: Keithley **2400S-900-01 Rev. K, September 2011**, [manufacturer PDF](https://download.tek.com/manual/2400S-900-01_K-Sep2011_User.pdf).

The API covers the command headers in sections 16–18 and the SCPI additions in Appendices F/G. Optional path keywords, long/short spellings, default subsystem indexes, and equivalent aliases share the indicated implementation; they do not require separate wrapper functions. Numeric setting properties accept documented `MIN`, `MAX`, and `DEF` parameters where applicable. Properties normally query the current value. The metadata properties below expose the documented numeric query modifiers.

| Reference | Python command map |
| --- | --- |
| Section 16: IEEE-488.2 common commands | [System/common commands](system_commands.md) |
| Section 17: configure, read, fetch, measure | [Signal-oriented commands](system_commands.md) |
| Table 18-1: CALCulate1/2/3 | [Calculation commands](calculation_commands.md) |
| Table 18-2: DISPlay | [Display commands](calculation_commands.md) |
| Table 18-3: FORMat | [Format commands](calculation_commands.md) and table below |
| Tables 18-4/5: OUTPut, ROUTe | [Output/routing commands](source_sense_commands.md) |
| Tables 18-6/7: SENSe, SOURce, SOURce2 | [Source/sense commands](source_sense_commands.md) |
| Table 18-8: STATus | [Status commands](calculation_commands.md) |
| Tables 18-9/10/11: SYSTem, TRACe, TRIGger/ARM | [System/buffer/trigger commands](system_commands.md) |
| Appendix F: contact-check limits and sequence 2 | [Calculation](calculation_commands.md), [System](system_commands.md) |
| Appendix G: MEP SCPI controls | [System](system_commands.md) |

All command implementations live in `src/keithley2400/keithley2400.py`. Documentation is split by subsystem for lookup; the library itself has no subsystem base classes or endpoint objects.

Reading format settings are direct properties:

| Command | Python API |
| --- | --- |
| `:FORMat[:DATA] <type>[,<length>]` / `?` | `data_format` |
| `:FORMat:BORDer <name>` / `?` | `byte_order` |

`check_errors()` composes the shared `read_error()` operation. The Python-only `check_errors_after_write` flag controls automatic queue checks; it is not a SCPI setting.

The manual's detailed references take precedence over conflicting summary tables. For example, the detailed output-enable reference uses `:OUTPut:IENABle:STATe`, while the summary lists `ENABle`; the tripped query separately uses `:OUTPut:ENABle:TRIPped?`. Composite-limit and math command discrepancies are noted in their command map. These paths remain hardware-validation uncertainties, rather than grounds for guessing alternate responses or retrying alternate commands.

The manual specifies no calibration-service command set. Calibration procedures from a separate service manual and the alternative non-SCPI 488.1 protocol are outside this SCPI command map. Bus-level control lines such as IFC/GET are VISA/controller operations, not additional SCPI headers.

## Numeric query modifiers

Each read-only member ending in `_minimum`, `_maximum`, or `_default` issues exactly one documented query: `? MIN`, `? MAX`, or `? DEF`, respectively. It returns the numeric response directly and does not request the other values.

```python
minimum = meter.source_voltage_level_minimum
maximum = meter.source_voltage_level_maximum
reset_default = meter.source_voltage_level_default
```

The following table lists the prefixes to which those three suffixes apply:

| Manual numeric command | Member prefix |
| --- | --- |
| Source current/voltage level, range, triggered level, start, stop, center, span, step | `source_current_level`, `source_current_range`, `source_current_triggered_level`, `source_current_start`, `source_current_stop`, `source_current_center`, `source_current_span`, `source_current_step`, and the corresponding `source_voltage_*` prefixes |
| Sense current/voltage/resistance range and NPLC | `sense_current_range`, `sense_current_nplc`, and the corresponding `sense_voltage_*` / `sense_resistance_*` prefixes |
| Sense current/voltage compliance | `current_compliance`, `voltage_compliance` |
| Sense averaging count | `average_count` |
| Source voltage protection, delay, sweep points, pulse width/delay | `voltage_protection`, `source_delay`, `sweep_points`, `pulse_width`, `pulse_delay` |
| Digital auto-clear delay | `digital_clear_delay` |
| Display digits | `display_digits` |
| Trace points | `trace_points` |
| Arm/trigger count, arm timer, trigger delay | `arm_count`, `trigger_count`, `arm_timer`, `trigger_delay` |

Indexed numeric limit thresholds (2, 3, 5–12) use `get_limit_upper_minimum(index)`, `get_limit_upper_maximum(index)`, and `get_limit_upper_default(index)`, with equivalent `get_limit_lower_*` methods. Each method also performs only its one documented query.

Transfer-format fixtures use the canonical short responses `ASC`, `REAL`/`SREAL`, `NORM`, and `SWAP`. The manual names the allowed parameters but does not explicitly illustrate every query readback spelling. Those readbacks, and the conflicting command spellings noted above, still need hardware confirmation; the driver does not silently try alternate spellings.
