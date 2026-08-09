"use client";

import { Candidate, Project } from "@/lib/types";
import { Badge, StatusDot } from "@/components/ui";
import { IconCheck, IconStar } from "@/components/icons";
import { thumbUrl, compactLicense } from "@/components/helpers";

/**
 * A single selectable image candidate — used in both the Visuals step
 * (project-level grid) and the per-scene inspector drawer.
 */
export function CandidateCard({
  project,
  candidate,
  selected,
  onSelect,
}: {
  project: Project;
  candidate: Candidate;
  selected: boolean;
  onSelect: () => void;
}) {
  const url = thumbUrl(project, candidate);
  return (
    <div
      onClick={onSelect}
      className={`group relative rounded-lg overflow-hidden border cursor-pointer transition-all
        ${selected ? "border-primary ring-1 ring-primary/60" : "border-edge hover:border-edge2"}`}
    >
      {url ? (
        <img src={url} className="w-full aspect-[4/3] object-cover" alt="" loading="lazy" />
      ) : (
        <div className="w-full aspect-[4/3] bg-panel grid place-items-center text-faint text-2xs">
          {candidate.provider}
        </div>
      )}
      <div className="absolute inset-x-0 bottom-0 flex items-center justify-between gap-1 px-1.5 py-1 bg-gradient-to-t from-black/80 to-transparent">
        <span className="text-[10px] text-white/80 truncate">{compactLicense(candidate.license)}</span>
        {selected ? (
          <span className="text-primary2">
            <IconCheck width={13} height={13} />
          </span>
        ) : (
          <span className="text-white/40 group-hover:text-white/80">
            <IconStar width={12} height={12} />
          </span>
        )}
      </div>
    </div>
  );
}

/** Small labelled select used across inspector fields. */
export function SelectInput({
  value,
  options,
  onChange,
  placeholder,
}: {
  value: string;
  options: string[];
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="input w-full h-9 appearance-none"
    >
      {placeholder && <option value="">{placeholder}</option>}
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}
