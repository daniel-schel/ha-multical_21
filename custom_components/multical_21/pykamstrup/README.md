# PyKamstrup
This is an implementation of the Kamstrup Meter Protocol (KMP) based
on reverse engineering of a traffic dump.

## Contributors
This file has seen many modifications over the years, contributions have been made by:
| Author | Profile | Notes | Source |
|--|--|--|--|
| Poul-Henning Kamp | [@bsdphk](https://github.com/bsdphk) | Original author | https://github.com/bsdphk/PyKamstrup |
| Erik Jensen |  | Provided units and exponents |  |
| Frank Reijn | [@freijn](https://github.com/freijn) |  |  |
| Paul Bonnemaijers |  |  |  |
|  | [@adabrandt](https://github.com/adabrandt) | Support reading of multiple values at once | https://github.com/bsdphk/PyKamstrup/pull/6 |
| Sander Gols | [@golles](https://github.com/golles) | This component for Home Assistant |  |

There might be other significant contributors that I'm not aware off, feel free to add them in a PR.

## Observed Multical 21 registers

The following register observations were collected with the manual KMP scan in
the Home Assistant integration. The register number is encoded as a
big-endian two-byte value at the beginning of the response. The register
address alone does not define the meaning of a value; names below remain
neutral where the meter semantics have not been confirmed.

### Confirmed registers

| Register | Hex | Observed type or unit | Observation |
|--:|--:|--|--|
| 68 | `0x0044` | volume, `m3` | Main volume register (`V1`) |
| 74 | `0x004A` | flow, `L/h` | Main flow register |
| 98 | `0x0062` | `yy:mm:dd` | Short meter date |
| 99 | `0x0063` | information | Integer-like information value |
| 113 | `0x0071` | information | Readable, meaning unconfirmed |
| 138-141 | `0x008A-0x008D` | date, volume/flow | Flow history records 1 and 2 |
| 153 | `0x0099` | ASCII | `0100200053533` |
| 154 | `0x009A` | information | `62145` |
| 155 | `0x009B` | `Wh` | `0` at scan time; meaning unconfirmed |
| 222 | `0x00DE` | information | `0` |
| 223 | `0x00DF` | `L` | `0` at scan time |
| 237-240 | `0x00ED-0x00F0` | information/volume | `239` returned `79429.271 L`; other values need observation |
| 241-242 | `0x00F1-0x00F2` | `L/h` | `0` at scan time |
| 243 | `0x00F3` | `m3` | Reverse volume (`V1Reverse`), `0.003 m3` at scan time |
| 244 | `0x00F4` | information | `0` |
| 253 | `0x00FD` | information | `0` |
| 254 | `0x00FE` | ASCII | `2146C0K842` |
| 261 | `0x0105` | Bitfield | `2` |
| 262-265 | `0x0106-0x0109` | information/Bitfield | `10000`, `2`, `0`, `0` |
| 292-305 | `0x0124-0x0131` | temperature, `deg C` | Mostly `18-27 deg C`; register `298` returned `128 deg C` |
| 306-310 | `0x0132-0x0136` | information | `8`, `1`, `16`, `28`, `1` |

The protocol unit codes observed for special values include:

| Unit code | KMP type |
|--:|--|
| 37 | temperature (`deg C`) |
| 39 | volume (`L`) |
| 40 | volume (`m3`) |
| 41 | flow (`L/h`) |
| 51 | no physical unit |
| 54 | ASCII text |
| 59 | Bitfield |

### Unresolved or suspicious responses

Registers `248-252` (`0x00F8-0x00FC`) all returned the same 16-byte payload
and were decoded as the same unrealistic numeric value (`1.5459e38`). They
are treated as a structured data block or reserved area, not as scalar
sensors.

The values of registers `154`, `155`, `222-244`, `261-265`, and `306-310`
are readable, but their application-specific meanings have not been proven.
In particular, a zero value does not mean that a register is unused. Meaning
should be inferred by observing changes during water flow, temperature changes,
or other known meter events. Register `298` should also be monitored to
determine whether `128 deg C` is a sentinel value.

### Search history

The following ranges have already been queried with the manual scan. The scan
was performed in small blocks to limit optical-bus activity on the battery
meter.

| Searched range | Result |
|--|--|
| `0-63` | No additional readable registers found |
| `64-95` | Main values `68` and `74`; `86`, `87`, and `89` rejected by the meter |
| `96-127` | Registers `98`, `99`, and `113` readable |
| `128-141` | Registers `138-141` readable |
| `142-157` | Registers `153-155` readable |
| `156-172` | No additional useful values found |
| `173-189` | No additional useful values found |
| `190-206` | No additional useful values found |
| `207-223` | Registers `222` and `223` readable |
| `224-240` | Registers `237-240` readable |
| `241-257` | Registers `241-244`, `248-252`, `253`, and `254` readable; `248-252` look like a shared data block |
| `258-274` | Registers `261-265` readable |
| `275-291` | No additional useful values found |
| `292-308` | Registers `292-308` readable; temperatures are in `292-305` |
| `309-325` | No additional useful values found |
| `992-1008` | Registers `1001-1005` readable; these are mainly identification, time, date, or metadata |

The ranges `266-291` and `309-325` were also checked again as targeted
follow-up scans and produced no new useful responses. Some scan commands used
overlapping boundaries, so the table describes the effective coverage rather
than every individual command.

### Ranges for a future scan

The following areas have not been confirmed as searched in the scan history:

| Range | Reason to scan |
|--|--|
| `311-327` | Immediately after the temperature and status block |
| `328-344` | Continuation of the low-number register area |
| `1009-65535` | Not searched; a complete scan is not recommended for a battery-powered meter |

The next practical scan would therefore be `311-327`, followed by `328-344`
only if the first block contains useful responses. New readings should first
be observed over time before they are assigned a physical meaning or added as
regular sensors.

## License
`kamstrup.py` has it's own license, from the original author:
```
"THE BEER-WARE LICENSE" (Revision 42):

<phk@FreeBSD.ORG> wrote this file. As long as you retain this notice you can do whatever you want with this stuff. If we meet some day, and you think this stuff is worth it, you can buy me a beer in return Poul-Henning Kamp
```
