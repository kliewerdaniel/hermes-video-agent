"use client";

import { useState } from "react";
import { useJob } from "@/lib/api";
import { Badge, Spinner } from "./ui";

/** Fires a backend job, shows a live status chip, and refetches on completion. */
export function JobRunner({
  label,
  run,
  onDone,
}: {
  label: string;
  run: () => Promise<{ job?: string } | unknown>;
  onDone: (ok: boolean) => void;
}) {
  const [jobId, setJobId] = useState<string | null>(null);

  async function start() {
    const res = (await run()) as { job?: string };
    if (res?.job) setJobId(res.job);
    else onDone(true); // synchronous route returned the project directly
  }
  const status = useJob(jobId, (ok) => {
    setJobId(null);
    onDone(ok);
  });

  if (status.state === "running") {
    return <Spinner label={label + "…"} />;
  }
  if (status.state === "error") {
    return (
      <span className="inline-flex items-center gap-2">
        <Badge tone="danger">failed</Badge>
        <button className="text-xs text-muted underline" onClick={start}>
          retry
        </button>
      </span>
    );
  }
  return (
    <button
      className="text-sm text-primary2 hover:text-primary underline-offset-2 hover:underline"
      onClick={start}
    >
      {label}
    </button>
  );
}
