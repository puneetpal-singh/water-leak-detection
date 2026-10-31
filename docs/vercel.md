# Vercel and portfolio deployment

This demo is a static browser application: no Python process, function, database
or model inference runs on the hosting platform. The analysis and model results
remain in the research repository.

## What was optimized

- Official Plotly Cartesian 3.6.0 replaces the full chart bundle. It supports every
  chart type used by the dashboard. Its pinned SHA-256 is checked during export;
  the vendor's license header is preserved.
- Regular timestamp arrays are encoded as start, interval and count. Source
  wall-clock timestamps are reconstructed without a timezone or DST conversion.
- Sensor anomaly flags are packed into bits. Measurement values retain three
  decimals and anomaly scores five, matching the browser display precision.
- JSON assets are gzip files with content-hashed filenames. Browsers decompress
  these files using DecompressionStream, supported by current major browsers.
- Network geometry/correlation, operating patterns and PR curves load by view.
  Only ten decoded files are retained in the browser's request cache; concurrent
  requests for the same file share one fetch.
- Plotly loads on the first visible chart. Below-fold charts render as they
  approach the viewport; the text-only methodology page needs no chart library.

See `results/web_performance.json` for measured package sizes and local gzip
estimates. The original baseline is preserved separately. Gzip estimates are not
a measured Vercel network trace. CDN compression and browser caching can differ.

## Existing React/Vite portfolio

From this repository, after exporting browser assets:

```powershell
python scripts/prepare_portfolio.py C:/path/to/portfolio-puneet
```

This copies only the static demo into `public/demos/water-network/`. Link to
`/demos/water-network/index.html` from a project card using a normal anchor.
The existing portfolio integration includes that card, a small SVG preview drawn
from real measurements, and a link back to the portfolio's projects page.

The demo is a separate document, so its renderer and datasets are not imported
into the React application or fetched by homepage route preloading. Existing
portfolio security headers remain in place. Only demo asset caching is added:

```json
{
  "source": "/demos/water-network/assets/(.*)",
  "headers": [{"key":"Cache-Control","value":"public, max-age=31536000, immutable"}]
}
```

Revalidate `/demos/water-network/manifest.json` rather than caching it immutably.
Preserve all other portfolio headers and routes. Do **not** manually add
`Content-Encoding: gzip` to `.json.gz` files: they are binary gzip assets which
the application decompresses after fetching. They work with ordinary static HTTP
hosting and do not require a special server-side compression configuration.

## Standalone Vercel project

The root `vercel.json` selects a static Node-only build:

```text
node scripts/build_web.mjs
```

Output is `dist/`. Dependency installation is skipped; the required browser
assets are committed. `.vercelignore` excludes the research data, notebooks and
other non-hosting files from CLI uploads. Python is needed only to regenerate
the analysis/export, not for deployment or visitors.

## Regenerate and verify

```powershell
python scripts/export_dashboard.py --web-only
python scripts/verify_results.py
node --test tests/web.test.cjs
python scripts/measure_web.py
node scripts/build_web.mjs
```

`--web-only` preserves research figures and executed notebook outputs. Artifact
verification compares all sensor values, packed anomaly flags, event measurements
and score arrays against the saved research experiment. No detector parameters
or evaluation results change during website optimization.
