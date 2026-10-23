# Care team review frontend

This React/Vite client submits patient text and optional lab, radiology, or ECG uploads to the FastAPI `/api/runs` multipart endpoint. It renders durable named SSE events from `/api/runs/{run_id}/events` as they arrive.

Run the backend on port 8000, then:

```powershell
npm.cmd ci
npm.cmd run dev
```

Open `http://127.0.0.1:5173`. Vite forwards `/api` to the backend.

The form accepts up to ten files. Each file is labelled as a lab report, radiology image, or ECG image before submission. The client accepts named and ordinary SSE messages and closes the stream on every supported terminal run state.
