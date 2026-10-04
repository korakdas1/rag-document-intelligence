# Kestrel wet-season operations notebook

Record KFS-N, compiled 28 August 2024. Original synthetic field notebook. Entries combine operational narrative with observations from a fictional monitoring season. An explicit amendment corrects the heater-energy unit later in the archive; unrelated disagreements remain open.

## 1. Station history and opening checks

Kestrel Field Station was established in 2012 to maintain the Northfen Spur observation site.
The present wet-season study uses the existing service shelter, but its sample definition is narrower than the station's entire history. Older equipment checks remain in the maintenance folder. They should not be counted as observations from the current seasonal comparison simply because they use the same station name.

Kestrel crews compare the crest sensor with a portable reference at dawn before starting a staffed exposure run.
The dawn comparison reduces the effect of handling a warm instrument immediately after transport. It does not eliminate every environmental difference between the portable reference and the fixed sensor. The collector records the reference serial and any delay between arrival and comparison. A late visit is recorded as late rather than assigned the planned start time.

The Kestrel charging panel has a peak rating of 9 W.
That rating describes a panel under its specified condition, not continuous energy delivered to the logger. Cloud cover, orientation, and the charging controller affect actual delivery. The notebook keeps the panel rating separate from integrated heater energy and from the logger's operating state so that a reader cannot infer battery capacity from one familiar number.

## 2. Route and custody

Crews travel to the crest with sealed controls and return with the same custody envelope. A second person checks the envelope before the vehicle leaves the receiving area. The check catches a missing label while it can still be corrected from a witnessed setup, rather than after containers have been mixed. It is a custody control, not an additional environmental observation.

The service track crosses a drainage cut near the last bend. After rain, the route inspection can delay access even when the station continues to log. The access log and instrument log therefore use separate status fields. A missing site visit must not automatically become a sensor outage, and a sensor outage must not be explained as weather merely because the route was also difficult.

At receipt, staff photograph damaged sleeves before moving the containers. The image preserves the position of the label and seal but cannot establish the contents' measurement quality. The custodian matches the image to the field entry and notes any uncertain identity. A likely match is not silently promoted to a confirmed match to make the seasonal inventory balance.

## 3. Reference maintenance

The manual rain gauge is cleared and inspected before a reading is accepted. Debris is described in the field note rather than represented by a guessed correction. A blocked reference can explain why an interval is unusable for validation even when the automatic channel produced a smooth series. The absence of a valid reference should not be counted as a successful comparison with an assumed zero.

The portable temperature reference is allowed to stabilize before use. Staff record whether the shield is dry and whether the collector has recently handled the sensing face. These practical details can explain a transient difference without assigning a permanent calibration error. The notebook uses condition flags so that later analysis can distinguish a stable exposure from a disturbed setup.

Reference equipment and study sensors have separate serial ledgers. A replacement reference does not rename the fixed sensor or erase previous comparisons. The handover includes a link between the old and new reference entries, with the reason for replacement. That link is necessary when a seasonal plot spans equipment changes that are invisible in a simple list of sample timestamps.

## 4. Sampling and exclusions

The logger emits regular environmental samples and irregular diagnostic events. Diagnostics can be more frequent during a fault, so counting every message would exaggerate observation density precisely when the equipment is least stable. The export identifies message type before any completeness calculation. Reviewers compare accepted environmental samples with the expected schedule for the method revision in effect.

Fog-wetted shields are flagged separately from dry exposures. A wetting flag is not a measured correction, and the team did not subtract an assumed temperature bias from those readings. The affected data remain available for inspection but outside the defined dry-condition bias estimate. This exclusion preserves the intended comparison at the cost of leaving a real operating condition unquantified.

The notebook records reasons for rejected comparisons in plain language. A reason such as reference unavailable does not imply that the study sensor was inaccurate. A reason such as mismatched serial does not imply that the weather was unusual. Keeping these causes distinct prevents a single failure count from hiding the difference between instrument behavior and uncertainty about the evidence itself.

## 5. Seasonal comparisons

Kestrel accepted 31 paired rain-gauge comparisons after reference checks.
The accepted count describes paired observations, not calendar days or the number of regular logger samples. More automatic readings can fall within a single reference interval. Staff did not treat those repeated readings as independent reference comparisons. The seasonal table preserves the pairing identifiers so the effective sample definition remains visible.

Kestrel's largest observed dry-condition temperature bias was 0.7 degrees Celsius at the unshielded test mount.
The statement identifies both the condition and the mount. It is not a correction to be applied to every station reading. The shielded mount and the fog-wetted intervals answer different questions. The report does not claim an all-weather accuracy from a maximum observed in a restricted comparison, nor does it assign the same bias to an instrument at another site.

The team reviewed the pairings before comparing the result with the intended monitoring use. A convenient-looking time match was insufficient if the reference and study channel referred to different locations. Location labels were checked against the deployment diagram, and ambiguous pairs were retained as unresolved. Removing them from the accepted table did not remove them from the custody record.

## 6. Energy worksheet and unit caution

The original Kestrel notebook summary lists dew-heater energy as 0.64 MWh per day.
This is the original summary entry, preserved for comparison with the explicit correction in the method amendment. The meter export has its own unit label and integration interval. Readers should consult the correction before using the summary as a current energy value. The panel's peak rating is not an alternative way to infer the measured heater total.

Power leads were inspected during each staffed visit. An intact lead and an illuminated status light indicate a working connection at that moment. Neither observation yields a quantitative battery state after a storm. The field team did not install a separately validated state-of-charge measurement for that incident, so the archive cannot support a precise remaining-capacity answer.

When the heater is disabled for inspection, the logger can continue collecting other channels. The export retains that operating-state flag. A daily energy total without the flag could conceal that the device was not asked to operate for the whole interval. Staff therefore preserve the interval definition beside the integrated reading instead of comparing totals from incompatible operating schedules.

## 7. July restoration record

The Kestrel notebook records 6 hours to restore telemetry after the 26 July outage.
Restoration means the first stable remote telemetry stream. The incident note uses the same definition but reports a different duration. Neither document establishes authority over the other, and the joint reconstruction remained unsigned. A later correction to the heater-energy unit does not settle this timing disagreement. A summary must retain both values and their unresolved status.

The crew copied the local buffer before restarting the communications link. That copy can help determine what the logger observed while the remote display was unavailable. It cannot by itself identify when every remote client resumed receiving data. The investigation kept local acquisition evidence and remote telemetry evidence separate so that one clock would not silently stand in for another.

## 8. Interpretation and future work

The seasonal results support a bounded description of the maintained sites and accepted conditions. They do not measure species abundance, general station reliability over many years, or every possible form of wet-weather exposure. The notebook includes plausible reasons why those questions matter, but relevance is not the same as evidence. A future study would need to define and collect the missing variables.

Changing the regular sampling interval affects buffer handling and completeness calculations. It does not retroactively improve the physical observation represented by an old reading. The team retained the original cadence labels when preparing the mixed-season export. Analysts can then compare like intervals or describe the method change explicitly, without pretending that one uninterrupted protocol governed the entire archive.

## 9. Archive and release checks

Kestrel retains sealed comparison samples for 42 days after receipt.
The interval applies to the physical controls, not to every electronic record. The custodian checks the receipt date on the envelope before marking a sample for routine expiration. An unresolved custody issue creates a separate hold, and the hold must remain visible in the inventory. A copy of the worksheet does not replace the physical retention decision.

Kestrel releases a seasonal data package only after both the field custodian and the analysis reviewer sign it.
The signatures answer different questions. The custodian checks that the source package matches the field record; the reviewer checks that exclusions and derived tables follow the stated method. One signature cannot substitute for the other. A package can be analytically tidy yet still lack a traceable source envelope, or fully traceable yet contain an unexplained exclusion.

The release manifest points to the relevant protocol revision, the incident note, and any explicit amendment. Staff open those links from the receiving machine before accepting the handover. This final check tests whether another person can reconstruct the evidence chain. It does not create a new scientific result or resolve the open telemetry disagreement by administrative completion.
