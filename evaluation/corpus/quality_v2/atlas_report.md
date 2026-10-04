# Atlas retrieval operations and evidence audit

Record ARP-O, completed 21 October 2024. Original synthetic research report. Atlas is a fictional study of an authored manual archive. All measurements below are part of that fictional record, not a baseline for the repository containing it.

## 1. Frozen inputs

Atlas's frozen source inventory contains 240 manual files.
The inventory counts files before paragraph segmentation. A file can yield several passages, and the same equipment family can have several revisions. Neither a passage count nor a family count is interchangeable with the inventory count. The custodian checks the file list and byte digests before the operator starts a run, so a later source correction cannot silently change the meaning of the experiment.

Atlas froze its comparison question list on 2 October 2024.
The freeze preceded the system comparisons described in this report. A wording correction after that date would require a new query-list revision and a separate record of which runs used it. The team retained questions with awkward but understandable engineering phrasing. Replacing them with the vocabulary favored by one system would change the comparison rather than explain its result.

Atlas excludes manuals without a revision identifier from current-procedure comparisons.
An unversioned manual can still be retained for archive research, but it cannot establish which instruction is current. This rule is applied when constructing the comparison set, not after inspecting the retrieved passages. The exclusion ledger preserves the source filename and reason so that another reviewer can distinguish a missing revision from a missing document.

## 2. Source preparation

The importer records the original filename, the declared revision, and the extracted section path. Section headings provide useful context but do not establish authority by themselves. A heading named final result can appear in a retired manual. The source's revision status must therefore remain attached to the passage through retrieval, export, and review.

The team inspected a sample of paragraph boundaries before freezing the source package. A warning was raised when an identifier was separated from the sentence that defined it. Such a warning concerns the representation of source evidence, not whether a particular retriever ranks it well. Repairs to malformed extraction must be documented and applied before the comparison, so they do not become a way to favor a system after seeing its misses.

Tables were represented as simple text with their row and column labels preserved. The importer did not infer an omitted unit from a neighboring table in another document. If the source itself lacked a unit, the extracted record remained incomplete. That choice avoids an apparently helpful repair that could invent evidence. Reviewers can distinguish a source omission from a parser omission only when the original source remains available.

## 3. Reference review

Reference reviewers read the requested entity, time scope, and version constraint before choosing a passage. A good lexical match could still be irrelevant if it answered a historical question while the request concerned the current procedure. The label form required a short explanation for these cases. The explanation was not shown to the retrieval operator while selecting a run configuration.

Two reviewers worked independently on disputed examples before meeting. They compared the exact source statements instead of starting from a system-generated summary. When a question admitted more than one compatible passage, both could be recorded as evidence. When two sources actually disagreed, the disagreement was retained rather than averaged into an invented consensus. The review process therefore distinguishes redundancy from conflict.

The source inventory also contains near-duplicate maintenance instructions. Their similarity is intentional: changing a numeric limit or an approval qualifier is common in a revision history. Reviewers checked whether a later source explicitly superseded an earlier field. A later file date alone was insufficient. Independent notes can disagree without either being a correction, and the reference record must preserve that distinction.

## 4. Controlled retrieval fixtures

Atlas's dense stress fixture contains 90 candidate passages.
This fixture includes unrelated but lexically similar operating manuals as well as close revision pairs. It is a controlled exercise distinct from the smaller lexical fixture in the methods memo. The counts describe the authored experiments, not suggested settings for another application. Comparing their timings requires naming both the fixture and the endpoint being timed.

The operator checked that an exact equipment code could be found without using an undocumented alias. Aliases were tested separately, with the alias map included in the run package. This separation prevents a query expansion from looking like evidence that the source contained the original spelling. A successful result should be explainable from the preserved query and configuration, not from an operator's memory of an ad hoc adjustment.

The run ledger names the source inventory, query list, and configuration for each execution. A rerun with a different source revision receives a different ledger entry even when all visible questions are unchanged. Staff do not combine the best per-question result from several runs into a single score. Such a mixture would lack a configuration that another operator could reproduce.

## 5. Timing and citation observations

Atlas measured 36 ms for retrieval at the 95th percentile and 36 s for complete answer delivery at the 95th percentile.
The retrieval interval ends when the candidate list is available. Complete delivery includes subsequent work and the final output. The same numeric part does not make the two latencies equivalent. A report that drops the unit or endpoint would hide most of the user's wait while appearing to quote a recorded measurement accurately.

In Atlas's citation-export check, 7 of 60 answer records lost their source labels.
The check concerned exported records, not whether the underlying retrieval returned a relevant passage. Reviewers traced each affected record through the export path and kept the denominator fixed. A source label surviving export also did not prove that the answer was entailed by the source. The audit separated evidence availability, citation transport, and claim support as different questions.

| Audit object | What a successful check establishes |
| --- | --- |
| Source inventory | The named files and digests are present |
| Passage export | Text and source revision travel together |
| Citation mapping | An output marker resolves to a named excerpt |
| Human claim review | A reviewer assessed the claim against the excerpt |

The table is a reading guide, not a list of equivalent accuracy measures. A system can pass one row and fail another. In particular, a syntactically valid citation can point to a passage about the wrong revision. The operations team resisted reducing these observations to a single grounded flag, because the flag would conceal where the evidence chain had broken.

## 6. Revision-sensitive examples

A maintenance instruction can retain its heading while changing its required interval. A retrieval system that favors the older, more frequently quoted version can therefore produce an answer that looks well supported but is wrong for a current-value request. Atlas preserves the old version because historical questions still need it. The review records whether the question asks for current, historical, or comparative evidence.

Some examples require both versions explicitly. A question about how a threshold changed is incomplete if the answer gives only the new value. Conversely, a question asking only for the current value need not reproduce every obsolete number. Reviewers distinguish completeness relative to the question from an indiscriminate preference for more citations. Extra historical evidence can confuse an answer when its status is not made clear.

The archive also includes independent notes with unresolved discrepancies. A release notice can correct an acceptance gate without settling an audit allocation maintained by another owner. The later notice's authority is limited to its explicit scope. This is why a reader cannot use document recency as a universal conflict-resolution rule across the entire project.

## 7. Error handling and repeatability

The importer distinguishes a possible alias from a confirmed source-path collision. A warning starts an inspection; a confirmed collision blocks the ambiguous mapping. Keeping the two states separate prevents a speculative warning from being reported as a demonstrated data error. It also prevents a serious collision from being dismissed as a harmless duplicate filename.

For each failed run, the operator preserves the original configuration and diagnostic output before attempting a retry. A successful retry receives a new record rather than replacing the failed one. This does not mean every transient failure belongs in a quality score, but it keeps reliability observations available for a separate operational analysis. The inclusion policy must be stated before comparing systems.

The report does not name a deployed language model or infer its parameter count from latency. It also does not measure electricity use or cost per session. A slow result could arise from several parts of the pipeline. Without measurements at the required boundary, the archive cannot convert a timing observation into one of those absent quantities.

## 8. Limitations and interpretation

The authored manuals make version-sensitive cases legible and repeatable. They cannot represent every writing style, document defect, or organizational convention found in an operational library. The study excludes customer documents and handwritten annotations. Those exclusions limit what its results can establish even when the internal reference review is careful and the source package is fully reproducible.

Reviewers can inspect every example in a modest archive, but that does not remove all judgment from a relevance label. Questions can have different reasonable levels of detail, and a concise gold passage may not enumerate every valid formulation of an answer. Atlas retains explanations for difficult labels so future comparisons can identify whether a change concerns system behavior or the reference definition itself.

## 9. Release and historical replay

Atlas retains rollback index-manifest snapshots for 14 days after release.
The snapshots support recovery of the exact source mapping used by the release. This interval is separate from the working reviewer-comment schedule. Removing a snapshot does not authorize removing the immutable source inventory or signed decisions. The custodian records which artifact class is expiring so a general cleanup instruction cannot erase the wrong evidence.

An Atlas historical replay must include the requested manual revision in its exported label.
The label lets a reviewer distinguish a deliberately historical answer from an accidental use of retired material. It remains necessary even when the equipment name and quoted sentence seem distinctive. Two revisions can share most of their text while disagreeing on the one field the question asks about. Revision identity is therefore part of the evidence, not optional presentation detail.

The handover package ends with unresolved audit items and links to the signed release. The recipient checks a current lookup and a historical lookup against their named source revisions as an archive-navigation exercise. That check does not create a new performance result. It confirms that the preserved package can still express the distinction on which later comparisons depend.
