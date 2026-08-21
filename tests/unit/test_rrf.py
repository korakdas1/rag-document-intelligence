from research_assistant.retrieval.fusion import RankedItem, ReciprocalRankFusion


def test_rrf_uses_one_based_ranks() -> None:
    fusion = ReciprocalRankFusion(k=60)
    fused = fusion.fuse(
        [
            [RankedItem("a", rank=1, score=0.9, retriever="dense")],
            [RankedItem("a", rank=1, score=12.0, retriever="lexical")],
        ]
    )
    assert len(fused) == 1
    assert fused[0].fused_score == (1 / 61) + (1 / 61)


def test_duplicate_chunks_are_merged() -> None:
    fusion = ReciprocalRankFusion(k=0)
    fused = fusion.fuse(
        [
            [
                RankedItem("a", rank=1, score=0.9, retriever="dense"),
                RankedItem("b", rank=2, score=0.8, retriever="dense"),
            ],
            [
                RankedItem("b", rank=1, score=10.0, retriever="lexical"),
                RankedItem("a", rank=2, score=9.0, retriever="lexical"),
            ],
        ]
    )
    ids = [item.chunk_id for item in fused]
    assert ids == ["a", "b"] or len(ids) == 2
    assert len(ids) == len(set(ids))
    both = {item.chunk_id: item for item in fused}
    assert set(both["a"].ranks) == {"dense", "lexical"}
    assert set(both["b"].ranks) == {"dense", "lexical"}


def test_tie_break_is_deterministic() -> None:
    fusion = ReciprocalRankFusion(k=60)
    left = fusion.fuse(
        [
            [RankedItem("b", rank=1, score=1.0, retriever="dense")],
            [RankedItem("a", rank=1, score=1.0, retriever="lexical")],
        ]
    )
    right = fusion.fuse(
        [
            [RankedItem("a", rank=1, score=1.0, retriever="lexical")],
            [RankedItem("b", rank=1, score=1.0, retriever="dense")],
        ]
    )
    assert [item.chunk_id for item in left] == [item.chunk_id for item in right]
    assert left[0].fused_score == left[1].fused_score
    assert left[0].chunk_id < left[1].chunk_id
