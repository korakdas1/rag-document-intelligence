# Operator Manual

Synthetic manual with distinct sections.

## Architecture

The KRON operator uses a dual-buffer scheduler.
Incoming tokens fill buffer A while buffer B is flushed to storage.

## Limitations

The KRON operator cannot process streams longer than 4096 tokens in a single pass.
Operators must split longer streams before submission.
