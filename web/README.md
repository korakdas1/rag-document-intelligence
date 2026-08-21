# Research Assistant UI

Vite + React + TypeScript client. It calls `/api/*` only. It does **not** implement retrieval, chunking, or generation.

```bash
npm install
npm run dev      # http://127.0.0.1:5173 (proxies /api → :8000)
npm test
npm run typecheck
npm run lint
npm run build
```

Start the API separately: `python -m research_assistant serve`
