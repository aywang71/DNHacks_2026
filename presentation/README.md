# wake.ai presentation

This is the wake.ai pitch deck. It is a Slidev deck with five slides, including
one live-demo slide.

From this directory:

```bash
npm install
npm run dev
npm run build
npm run export
```

To export directly to `rendered/wake-ai-pitch-deck.pdf`, run:

```bash
npm run render:pdf
```

`npm run export` is defined in `package.json` and runs Slidev export.

The deck is not wired to repository data. Its language reflects the current
presence viewer and its static model queue: GFW presence is hourly gridded
coverage, and the queue supplies review leads rather than findings.

The deck loads Google Fonts remotely. An offline demo may render with fallback fonts.
