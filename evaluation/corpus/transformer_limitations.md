# Transformer Limitations

Synthetic discussion of known modeling limits.

## Complexity

Self-attention has quadratic complexity in sequence length, which limits very long documents.
Sparse or linearized variants exist but are outside the scope of this note.

## Missing inductive bias

The authors note that the model does not include an explicit recurrence or convolution.
Position information must be added separately. Long-range copying still depends on attention.
