# Meridian validation protocol: draft D

Record MTS-PD, 20 March 2024. Formal method for the corridor C pilot. The release notice explicitly identifies later changes to the acceptance rule; this draft remains available for historical and subset review.

## Counting boundary

Meridian's sampling window is weekdays from 05:00 to 21:00.
The observer opens a new sheet at the beginning of each window and notes any interruption before restarting. Events outside the window are retained as equipment diagnostics but excluded from the comparison denominator. The window describes when the pilot measures activity, not when the transit service itself operates.

Meridian validation excludes weekend departures from its labeled sample.
A counter may continue to emit messages outside staffed collection periods. Such messages do not become labeled examples without a corresponding observer record. A downstream analyst must check the label flag rather than infer coverage from the presence of a timestamp. No correction factor is provided to turn the weekday sample into a weekend estimate.

## Method and calibration

Meridian counts a departure when a badge edge crosses the platform exit line, not when a fare is purchased.
The observer marks the crossing direction on a paper grid. Reversals near the line are reviewed before being assigned an event identity. A passenger who changes direction can generate several raw edge transitions but only one accepted departure. The paper grid is keyed to a short event interval; it does not carry a person's name or destination.

The reference board is walked through the exit line before collection starts. It checks that the counter and observer agree on the boundary, not that the counter recognizes every kind of passenger movement. A calibration walk with a large unobstructed board is easier to detect than a crowded departure. The calibration result must therefore be reported separately from operational detection accuracy.

## Draft acceptance rule

Meridian draft D proposes a minimum departure-detection score of 0.80.
The score is the fraction of accepted observer events matched under the protocol's time tolerance. It is not a probability attached to an individual passenger. The draft proposal does not become final merely because it appears on a signed setup checklist. Reviewers must consult the release notice for the current acceptance rule.

An unmatched message stays unmatched until the event ledger is reviewed. Staff must not widen the matching tolerance after seeing a difficult day. If a clock correction is needed, preserve the original offset and create a new matching pass with a separate identifier. That makes a revised calculation distinguishable from a more favorable selection of examples.

## Inspection responsibility

The Meridian protocol assigns Pavel Reed responsibility for corridor C inspection handoff in April 2024.
This is the same responsibility and month described in the brief. Neither assignment is marked as superseding the other. Equipment operators should request a joint clarification instead of assuming that the method's later issue date establishes staffing authority. The validation procedure can be followed while the named handoff owner remains unresolved.

## Exports

Each event export must retain:

- The observation window and the observer-label flag.
- Acquisition time separately from delivery time.
- The instrument configuration and exit-line setup identifier.
- A reason for each rejected or unresolved event.

Counter wake latency and server upload delay are different columns. The first is measured at the instrument; the second includes the network queue. A shared numeric value would not make those measurements interchangeable. Preserve the unit suffix in every exported column, and retain the event-state flag when copying a row into a summary.

The method does not require a face camera, an income survey, or a fare database. It cannot recover attributes that were never observed. A report may discuss the difficulty of crowded movements without containing a separate accuracy estimate for every rider subgroup.
