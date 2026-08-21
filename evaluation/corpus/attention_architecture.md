# Attention Architecture Notes

These notes summarize a development lecture on encoder-only Transformers.
They are synthetic teaching material, not a copy of any published paper.

## Self-attention

Self-attention computes a weighted combination of all token representations in the sequence.
Each token produces a query, key, and value vector. Compatibility between a query and a key
determines how much of the corresponding value is mixed into the output.

## Multi-head attention

Multi-head attention uses 8 parallel attention heads in the development configuration described here.
Heads can specialize in different syntactic or positional patterns. Outputs are concatenated
and projected back to the model width.

## History

The Transformer architecture was introduced in 2017.
The lecture treats that year as a historical marker, not as a claim about any licensed PDF.
