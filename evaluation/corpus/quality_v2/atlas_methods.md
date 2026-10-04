# Atlas methods memorandum: revision 1

Record ARP-M1, issued 16 September 2024. Synthetic research methods for the fictional Atlas manual archive. Later release notes explicitly identify changes to the acceptance rule.

## Split construction

Atlas assigns complete manual families to a split rather than splitting individual paragraphs at random.
A family includes its overview, operating method, and revision history. Keeping the family together avoids training a labeling convention on one paragraph and calling the next paragraph an independent held-out source. The split manifest is frozen before systems are run. The method does not guarantee independence from every shared engineering term across different families.

## Reference judgments

Atlas labels relevance before reviewers see system rankings.
Reviewers use the requested entity, date, and document status when choosing evidence. A passage can share all of a query's prominent words and still describe a retired version or a different fixture. The label record names the manual and quotes the decisive statement. An unexpected system result starts an audit of the evidence chain; it does not automatically become a new gold label.

Each disagreement is reviewed with the original wording visible. Staff distinguish a transcription mistake from a legitimate interpretive dispute. A transcription correction gets a new label revision with its reason recorded. An unresolved interpretive dispute remains marked rather than being hidden by a majority score. The experiment's reference quality depends on these decisions as well as on the retrieval implementation.

## Fixture sizes and acceptance

Atlas's lexical stress fixture contains 9 candidate passages.
The fixture intentionally places a current instruction beside older wording with similar identifiers. It is a small controlled exercise, not the size of the full corpus or a recommended production candidate depth. The dense fixture described in the operations report is a separate exercise. Their counts should not be substituted for one another when interpreting a timing result.

Atlas revision 1 proposes an evidence-recovery acceptance threshold of 84%.
The proposal applies to the defined audit worksheet and remains provisional until the release review signs a final gate. A measured recovery result and an acceptance threshold are separate fields. The presence of the proposal in a protocol does not prove that any system achieved it or that it is the correct gate for another corpus.

## Audit allocation

For Atlas review batch R9, the methods memorandum allocates 30 cases to the independent audit pool.
The limitations memorandum contains a different allocation for the same batch and audit definition. Neither document establishes precedence. The review chair requested a signed reconciliation, but neither author was authorized to overwrite the other's record. A later release of the retrieval fixture does not automatically resolve the allocation.

## Repeatability

The operator records the source manifest, query list, and configuration identifier before starting a run. Timing includes clearly named endpoints so retrieval duration can be distinguished from answer-generation duration. The memo does not prescribe settings for another system. Its numbers describe a fictional controlled study, and changing a host application's configuration is outside this record's purpose.

Queries asking for a current instruction must identify the applicable revision. Historical questions can intentionally request retired material. The labeler should not remove old manuals merely because they are plausible distractors; their status is part of the question the archive must answer.
