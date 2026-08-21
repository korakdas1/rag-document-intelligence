# Demo

About five minutes on a local machine. Use the original files in [examples/demo_documents/](../examples/demo_documents/). Do not demo private PDFs.

## Start

1. `ollama serve` and confirm `qwen2.5-coder:7b` (`ollama list`)
2. `python -m pip install -e ".[dev]"` (once)
3. `npm --prefix web install` (once)
4. `python -m research_assistant serve`
5. `npm --prefix web run dev`
6. Open http://127.0.0.1:5173
7. Optional: `curl -s http://127.0.0.1:8000/health` and `/ready`

## Add documents

Use **Add documents** or drop files onto the window to add one or more PDF, Markdown, or text files from `examples/demo_documents/`. Wait until they show **Ready**. Unsupported files in a mixed drop are skipped; the rest still upload.

## Questions

Keep **all documents** selected unless a step says otherwise.

| Step | Ask | What to look for |
| --- | --- | --- |
| Direct fact | Where did the Northline Depot open? | Northline, Vermont; click `[S#]` |
| Multi-document | Who does Lena Hart report to, and who maintains the validators? | Marcus Cho; Ilya Berg; sources from staff notes |
| Follow-up | After the previous turn: Who does she report to? | Same reporting line; Developer details show a rewritten retrieval query |
| Unsupported | When did the mountain tram open? | Insufficient evidence (tram is only mentioned as *not served*) |
| Off-topic leak | What city is the Eiffel Tower in? | Should not answer from general knowledge if you expect abstention on non-depot evidence — or answer only if the leaflet is selected. Prefer: leave all selected and ask a depot fact, confirming the Paris leaflet is not cited. |
| Subset | Select **only** `northline_limits.md`. Ask: How many shuttle vehicles does the depot have? | Insufficient evidence (fleet size is in overview, not limits) |

## Also show

- **Developer details** — retrieval vs generation latency; first-pass vs repair if markers were missing
- **Refresh the browser** — session turns and document scope persist
- **History** — open saved conversations; **New research** starts a new one without deleting the old session

## Screenshot

**TODO — human:** capture a clean window using only these synthetic files (no private PDFs). Missing screenshots do not block repository readiness.
