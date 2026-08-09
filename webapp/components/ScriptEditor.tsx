"use client";

import { useEffect, useState } from "react";
import { useWorkspace } from "@/components/Workspace";
import { Button, Badge, StatusDot } from "@/components/ui";
import { IconSpark, IconScript, IconWand, IconCheck } from "@/components/icons";

export function ScriptEditor({ onDone }: { onDone?: () => void }) {
  const { project, isBusy, saveScript } = useWorkspace();
  const [text, setText] = useState(project.script ?? "");
  const [editing, setEditing] = useState(false);

  // Keep the textarea in sync with the manifest. After "Generate with AI" the
  // backend returns a fresh script on `project.script`; if we only seeded text
  // once on mount it would never update and look like the generate did nothing.
  useEffect(() => {
    if (!editing) setText(project.script ?? "");
  }, [project.script, editing]);

  const dirty = text !== (project.script ?? "");

  const hasScript = !!project.script && project.script.trim().length > 0;

  // approximate downstream impact
  const downstream =
    project.scenes.length > 0
      ? "Editing the script will likely change the storyboard. Existing scenes are preserved — re-run Build Storyboard to resync."
      : null;

  return (
    <section id="rail-script" className="scroll-mt-4">
      <div className="flex items-center gap-2 mb-3">
        <IconScript width={16} height={16} className="text-primary2" />
        <h2 className="text-sm font-semibold tracking-wide">SCRIPT</h2>
        <span className="text-2xs text-faint">{text.length} chars</span>
        <div className="ml-auto flex items-center gap-1.5">
          {isBusy("script") && (
            <span className="flex items-center gap-1.5 text-2xs text-muted">
              <span className="h-3 w-3 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
              thinking…
            </span>
          )}
          <Button
            variant="secondary"
            size="sm"
            loading={isBusy("script")}
            onClick={() => saveScript(text, false)}
            disabled={!dirty || isBusy("script")}
          >
            Save
          </Button>
          <Button
            size="sm"
            loading={isBusy("script")}
            onClick={() => saveScript("", true)}
            title="Generate the script with AI"
          >
            <IconSpark width={13} height={13} /> Generate with AI
          </Button>
        </div>
      </div>

      <div className="inset p-1">
        <textarea
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setEditing(true);
          }}
          spellCheck={false}
          className="w-full h-44 resize-none bg-transparent p-3 text-[13px] leading-relaxed text-text/90 outline-none font-[15px]"
          placeholder="Write your script, or generate one with AI…"
        />
      </div>

      <div className="flex items-center gap-2 mt-2 text-2xs">
        {downstream && (
          <span className="text-warn flex items-center gap-1">
            <IconWand width={12} height={12} /> {downstream}
          </span>
        )}
        {text && !downstream && (
          <span className="text-success flex items-center gap-1">
            <IconCheck width={12} height={12} /> Script ready
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          {hasScript && onDone && (
            <Button size="sm" variant="secondary" onClick={onDone}>
              Next: Storyboard →
            </Button>
          )}
        </div>
      </div>
    </section>
  );
}
