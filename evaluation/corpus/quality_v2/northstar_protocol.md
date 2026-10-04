# Northstar Battery Pilot: protocol revision A

Record NBP-PA, issued 6 February 2024. Draft acceptance rules are retained here for historical comparison. The later signed amendment identifies which rules it supersedes; this file has not been silently rewritten.

## Baseline preparation

Northstar baseline packs are stored at 18 degrees Celsius before screening.
The storage condition is a preparation control, not a maximum operating temperature. A technician records arrival time before moving a pack into the warm room. The logger is allowed to stabilize with its lid closed so that handling heat does not become the baseline. A sample with a broken seal is held outside the run rather than assigned a convenient replacement serial.

The screening sample contains 48 cells selected after the receiving inspection. Incoming stock can be larger than the screening sample, because transport witnesses and damaged packaging are counted at receipt. The operator must preserve those two denominators. Capacity plots should identify the tested cells, not the count of objects on the receiving trolley.

## Rack method

Rack positions are randomized between Northstar screening runs to separate position effects from cell effects.
The randomized plan is signed before loading. Technicians may swap an unsafe holder, but the swap and its reason remain attached to the original plan. Calibration is repeated after a holder replacement. The trace includes a preparation interval, a charge interval, a rest interval, and a controlled discharge; a gap between intervals cannot be represented as a zero-current measurement.

Charging is limited to 2.8 A per cell, followed by a 25-minute rest. A surface probe is taped to the specified face of the enclosure. It measures that surface, not the cell core. The display uses the same temperature symbol for all channels, so the exported channel name is essential. No salt-spray exposure or cold-room capacity trial is included in this protocol.

## Provisional acceptance and inspection

Northstar revision A proposes a retained-capacity acceptance threshold of 74%.
This proposal is a gate for engineering discussion until the final acceptance notice is signed. Do not turn the proposed percentage into a production warranty. The report's observed retention is a measurement with its own denominator; it is not automatically the required acceptance level.

For the Northstar M2 warm-room bench, this protocol requires a harness inspection every 120 cycles.
The operations team maintained its own schedule for the same bench. The project has not assigned either schedule priority if the records disagree. Inspection events have their own timestamps and must not be inferred from a pause in the cycling plot. A safety stop can occur between scheduled inspections.

## Calibration fixture

The Northstar calibration fixture draws 36 mA while exercising the alarm indicator.
That load is deliberately larger than the pack's quiet standby load. It lasts only for the indicator check and must be excluded from the standby averaging window. Both readings may appear next to each other in a technician's export; the unit alone cannot distinguish them. The circuit label and operating state must travel with the value.

## Release record

The shift handover checklist is completed in order:

- Read back the rack serial and sample serial from the acquisition screen.
- Mark any incomplete cycle before copying a capacity result.
- Attach the operating-state note to each current measurement.
- Check the named acceptance revision before signing the pilot decision.

The protocol supports attended pilot testing after electrical inspection. It does not itself approve production deployment. A reviewer must check the release notice for a final decision and retain this revision as the historical method. Open questions about commercial service life, component prices, and coverage obligations are not resolved by passing the laboratory sequence.
