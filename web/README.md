## BACAP Digital Twin (web)

Next.js 15 (App Router, TypeScript) frontend for the quantum-optimized berth
allocation project. Renders an isometric react-three-fiber replay of a port
schedule from a static solution-artifact JSON (served from `public/artifacts/`),
with a timeline scrubber, synced Gantt strip, live KPIs, and side-by-side solver
comparison. No backend — artifacts are produced by the Python solvers.

## Getting Started

```bash
pnpm install
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000).

Checks: `pnpm lint && pnpm typecheck && pnpm test`.
