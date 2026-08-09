"use client";

import { useEffect } from "react";

// Next.js error boundary: any thrown error during render (e.g. a failed
// initial data fetch when the backend is momentarily down) lands here instead
// of white-screening the app.
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log so it shows up in the browser console for debugging.
    console.error(error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <div className="glass rounded-2xl p-8 max-w-md w-full text-center">
        <h1 className="text-xl font-semibold mb-2">Something went wrong</h1>
        <p className="text-muted text-sm mb-1 break-words">{error.message || "Unknown error"}</p>
        <p className="text-muted text-xs mb-6">
          The backend may be restarting. Try again — it usually recovers in a moment.
        </p>
        <button
          onClick={reset}
          className="px-4 py-2 rounded-lg bg-primary text-white text-sm font-medium hover:bg-primary2"
        >
          Retry
        </button>
      </div>
    </div>
  );
}
