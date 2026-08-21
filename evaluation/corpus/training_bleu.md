# Training and BLEU Notes

Synthetic lab notes on a translation training run.

## Optimization

Models were trained with the Adam optimizer and a warmup of 4000 steps.
The learning-rate schedule decayed after warmup. Batch size was 32 sequences.

## Evaluation metric

Translation quality was reported using BLEU on the WMT 2014 English-German test set.
BLEU here is a corpus-level n-gram overlap score. It is not a faithfulness metric for RAG.
