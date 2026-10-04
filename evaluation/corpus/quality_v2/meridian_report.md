# Meridian corridor C field operations report

Record MTS-OP, closed 3 May 2024. Original synthetic transit engineering report. The instrument, station, and measurements are fictional; the report illustrates how operational context can change the meaning of similar numbers.

## 1. Deployment and scope

Meridian observers labeled 3,600 departures during the initial staffed collection period.
The number counts accepted observer events, not raw radio messages. An accepted event may have several associated messages, especially when a rider hesitates near the exit line. Staff retained the message-to-event mapping rather than selecting one arbitrary message and discarding the rest. That mapping is needed to understand both duplicate detections and apparent gaps.

The Meridian corridor C pilot began on 8 April 2024 at Stone Arch platform.
The installation crew had visited earlier to mark the exit line and check access to power. Those visits did not collect the labeled operational sample. The project uses the first staffed collection day as its start date, so a setup photograph alone cannot establish that collection had begun. A later release notice marks another event in the same project history.

Meridian aligns the counter and observer clocks with a shared UTC beacon before each staffed window.
The beacon gives a common reference, not a guarantee that clocks remain aligned throughout a network interruption. The observer writes the measured offset before correction. Keeping that value makes it possible to distinguish an initial setup error from drift that develops later. The original offset is never replaced with an assumed zero in the exported log.

## 2. Station geometry

The counter faces a painted exit line beside the shelter. The line sits far enough from the door for an observer to distinguish a crossing from a person waiting under cover. Maintenance staff use a neighboring walkway, which is outside the measurement boundary. Their equipment may interrupt the view without becoming a passenger departure. The event sheet therefore has separate fields for an obstruction and a crossing.

An overhead sign and a drain cover help staff reproduce the setup position. These landmarks are easier to identify in a photograph than a tape measure placed on a crowded platform. A photograph is still only a configuration record. It does not show whether the counter detected every crossing during the rest of the day. The report pairs setup records with time-bounded observations instead of treating one image as proof of continuous performance.

The station's ordinary traffic includes people who pause, turn back, or walk alongside another rider. A useful operational test must include those movements without inventing a new event definition after the fact. Observers mark uncertain cases for review, and the reviewer sees the uncertainty flag. Removing every difficult movement would make the sample easier to label but less informative about the deployed boundary.

## 3. Label reconciliation

Two observers compare event sheets at the end of a window. They first reconcile timestamps and then review differences in crossing direction. Neither observer sees a per-event detection score while deciding the final label. The purpose is to make the reference ledger independent of whether the instrument appears successful. A disputed event remains flagged until the reconciliation note describes the decision.

The accepted sample excludes unstaffed intervals even when the counter is still running. Raw messages from those intervals help diagnose equipment behavior but do not have an independent departure label. Staff avoid calling them negative examples: the lack of an observer record does not imply that nobody crossed the line. The denominator must reflect the subset for which the reference method actually applies.

Copies of the event sheet preserve the original handwritten mark beside the typed transcription. A transcription correction receives its own note rather than a silent replacement. This makes it possible to audit a changed digit without assuming that the instrument or the observer made the original mistake. The process is slower than overwriting a spreadsheet cell, but it keeps the source of each change legible.

## 4. Calibration walks

The reference board follows the same marked route before each staffed window. Staff perform a forward crossing, a reversal, and a pause at the line. These movements expose timing and direction errors that a single brisk walk could miss. They are controlled checks, however, and do not represent the variety of crowded passenger movements. Calibration success must remain distinct from operational detection accuracy.

After a housing adjustment, the crew repeats the walk and records the reason for moving the instrument. A calibration result is associated with the new position only. It cannot retroactively validate events collected before the adjustment. When comparing intervals, reviewers check both the instrument configuration and the observer coverage so that a geometry change is not mistaken for a model improvement.

The validation worksheet uses words such as baseline, threshold, and release for different fields. The baseline describes a comparison condition, the threshold describes an acceptance rule, and release identifies an authorized configuration. None of those labels names a universal station accuracy. The report retains the full field names because short spreadsheet headings can make unrelated quantities look interchangeable.

## 5. Timing and measured results

Meridian's median counter wake latency was 24 ms; its median server upload delay was 24 s.
The first interval is measured from an instrument trigger to a ready counter. The second includes buffering and network delivery. Their equal numeric parts are accidental. A summary that omits units or merges the two columns would imply a timing behavior that the experiment did not observe. Staff keep both values beside their measurement endpoints when exporting the table.

Meridian's weighted departure-detection accuracy was 92.6% for the staffed weekday sample.
The weighting follows the accepted observation windows, not the count of radio messages. This result does not describe weekend demand or every subgroup of riders. The report contains no wheelchair-specific denominator. It also does not establish that the counter can safely control dispatch, since detecting a departure and making a control decision are separate operational questions.

The analysis table retains unresolved events as a separate count. They are not silently assigned to whichever class improves the headline result. Reviewers can therefore compare the accepted denominator with the original event ledger. A result without that denominator would be difficult to interpret even if its percentage were copied correctly. The report favors a traceable sample definition over a single detached accuracy number.

## 6. Outage ledger

For the Meridian corridor C outage on 18 April, the operations ledger counts 17 invalid pings.
The incident ledger reports another count using the same event window and validity definition. Neither ledger supersedes the other. Staff preserved both and requested a joint recount, which was still unsigned when this report closed. The difference must be reported as an unresolved disagreement rather than attributed to an undocumented change of denominator.

The raw outage bundle includes acquisition timestamps and delivery timestamps. A message delivered after service resumed may still belong to the outage interval. Sorting only by delivery time can move it into the wrong window. The recount procedure therefore starts from the acquisition record and records any missing timestamp explicitly. A missing timestamp is not a reason to invent one from neighboring messages.

The outage did not justify deleting the whole day from every analysis. Staff separated the affected window from unaffected staffed observations and recorded the rule used for each table. That separation is a data-handling decision, not a resolution of the conflicting invalid-ping count. The two ledgers remain independently named so a reader can locate the disagreement without searching through an unlabeled merged export.

## 7. Occlusion and operational interpretation

Strollers, baggage, and maintenance equipment can temporarily block the exit-line view. The observer records the obstruction along with the event interval. A visible badge edge and an actual passenger departure are related but not identical observations. The instrument can miss a visible event, and a reference observer can be uncertain about whether a partially hidden movement crossed the boundary.

These observations motivate caution about generalizing the aggregate result. They do not provide a measured rate for every kind of obstruction or rider. The study did not collect the linked attributes needed for such subgroup estimates. A user asking for a subgroup accuracy should receive that limitation, not a percentage borrowed from the overall staffed sample or from a controlled calibration walk.

## 8. Incident status and release boundary

The amplitude-drop investigation was still open when the early incident note was written. That note preserves a clock-related hypothesis, while the later release records the completed physical inspection. This report keeps the operational response and the cause decision separate. A cause statement should come from the document that explicitly closes the investigation, with the earlier hypothesis described as preliminary if it is mentioned.

The project also separates permission to observe from permission to control. An instrument release can authorize a stable pilot configuration without approving automatic dispatch. Reviewers should not infer a control authorization from the existence of a successful validation result. The ordinary station controller remains responsible for departures under the documented operating procedure.

## 9. Export and offline recovery

Meridian event exports are retained for 21 days after each observation window closes.
The signed method and release notices follow a separate archive schedule. An export contains event identifiers, time fields, and configuration labels, but no passenger face images or linked fare records. The custodian checks that the package contains the promised files before acknowledging delivery. A download confirmation by itself does not prove that every file in the manifest arrived intact.

After an offline interval, Meridian flags uncertain clock alignment instead of inventing replacement timestamps.
An analyst may later resolve some flagged intervals using preserved reference observations. Any such repair becomes a new derived table with its method recorded. The original acquisition data remain available. This makes a corrected analysis distinguishable from an apparently complete raw record that has silently acquired fabricated times.

The handover checklist asks the receiving analyst to open one event bundle and follow its links back to the setup record. This small end-to-end check often reveals a broken relative path that a file count would miss. It is an archive-integrity check, not a new detection experiment. Future experimental work should start with a frozen copy of the package and a clearly named comparison question.
