# CreatorPulse Vue MVP

This is the first Vue/Vite slice for CreatorPulse.

Current scope:

- Uses the existing static UI visual system from `05_UI设计/最终版/style.css`
- Implements the Growth Dashboard page
- Implements the Fans Analysis page
- Loads data from the Flask mock API
- Supports top-tab switching on both migrated pages

## Prerequisites

Start the Flask mock API from the repository root:

```powershell
python api\app.py
```

Install frontend dependencies:

```powershell
cd frontend
npm install
```

## Development

```powershell
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

The Vite dev server proxies `/api` to:

```text
http://127.0.0.1:5000
```

## Verification

Build:

```powershell
npm run build
```

Browser smoke test:

```powershell
npm run test:smoke
```

The smoke test expects both Flask API and Vite dev server to be running.

It verifies:

- the Vue page renders
- Chinese text is not mojibake
- Growth Dashboard and Fans Analysis can be opened from the sidebar
- all top tabs on both migrated pages switch
- no browser console errors are emitted
- desktop and mobile screenshots can be captured

Screenshots are written to `test-results/`, which is ignored by git.
