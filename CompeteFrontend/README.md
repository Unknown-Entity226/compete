# Compete Frontend

Compete is a React single-page app for viewing LeetCode profile stats, managing a friends list, and comparing profiles head-to-head.

## Run locally

Requirements: Node.js and npm.

```bash
npm install
npm run dev
```

The Vite development server runs on `http://localhost:5173` and proxies `/api` requests to the FastAPI service at `http://localhost:8000`. Start the backend using the instructions in the repository root README.

To point the frontend at a different API server, create a `.env.local` file with:

```dotenv
VITE_API_URL=https://your-api-host
```

## Build and lint

```bash
npm run build
npm run lint
```

The app includes sample profile data for the two preconfigured demo accounts when the profile service is unavailable. Other profile lookups and comparisons show the API error instead of substituting unrelated users.
