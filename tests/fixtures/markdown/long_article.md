# Background

The retrieval stage must surface passages that actually support the question rather than merely matching a few keywords. Dense vectors catch paraphrases; lexical scores catch rare identifiers. A research assistant that skips this distinction will hallucinate with confidence. This background section exists so the structure-aware chunker has a long first section to accumulate.

## Related work

Prior chat-with-PDF demos stuff entire files into a prompt. That fails as corpora grow and destroys citations. Hybrid retrieval, reranking, and evaluation are the usual remedies. This related-work section is intentionally a separate heading so chunk boundaries can follow the outline instead of a raw character window.

# Methods

We parse documents into ordered blocks with page and section locators, then chunk those blocks. The method is boring on purpose: no embedding-based semantic splits in this phase.

- keep code fences intact when they fit
- split only when a block exceeds max size
- record page ranges honestly

```python
def demo():
    return "code should survive chunking"
```

# Results

Structural metrics such as chunk count, size distribution, and section-crossing rate are what we can measure before retrieval exists. They do not prove quality. They only show whether the chunker does what it claims. This results section is another long-ish paragraph so both strategies have material to split or keep together depending on the configured target size.
