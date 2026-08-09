"use client";

import { motion } from "framer-motion";
import { STAGES, Stage } from "@/lib/types";

const LABELS: Record<Stage, string> = {
  script: "Script",
  scenes: "Shot List",
  visuals: "Visuals",
  narration: "Narration",
  draft: "Draft",
};

export function Stepper({
  approvals,
  current,
  onApprove,
  onReopen,
  busy,
}: {
  approvals: Partial<Record<string, boolean>>;
  current?: string;
  onApprove: (s: Stage) => void;
  onReopen: (s: Stage) => void;
  busy?: boolean;
}) {
  const curIdx = current ? STAGES.indexOf(current as Stage) : -1;
  return (
    <ol className="flex items-center gap-1 overflow-x-auto pb-2">
      {STAGES.map((s, i) => {
        const done = !!approvals[s];
        const isCurrent = i === curIdx;
        const reachable = i <= curIdx + 1 || done;
        return (
          <li key={s} className="flex items-center gap-1 shrink-0">
            <button
              disabled={!reachable || busy}
              onClick={() => (isCurrent || done ? onReopen(s) : onApprove(s))}
              title={done ? `Reopen from ${LABELS[s]}` : `Approve ${LABELS[s]}`}
              className="group relative flex flex-col items-center outline-none"
            >
              <motion.span
                animate={{
                  scale: isCurrent ? 1.08 : 1,
                  backgroundColor: done
                    ? "#50d890"
                    : isCurrent
                    ? "#7c6aff"
                    : "#1d1d2b",
                }}
                className="h-8 w-8 rounded-full grid place-items-center text-xs font-semibold border border-edge text-ink"
              >
                {done ? "✓" : i + 1}
              </motion.span>
              <span
                className={`mt-1 text-[11px] whitespace-nowrap ${
                  isCurrent ? "text-primary2" : done ? "text-success" : "text-muted"
                }`}
              >
                {LABELS[s]}
              </span>
            </button>
            {i < STAGES.length - 1 && (
              <span
                className={`h-px w-6 md:w-10 ${
                  done ? "bg-success/60" : "bg-edge"
                }`}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
