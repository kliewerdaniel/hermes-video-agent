"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Project } from "@/lib/types";
import { Button, Modal } from "./ui";

export function ProjectEditDialog({
  project,
  onClose,
  onSaved,
  onDeleted,
}: {
  project: Project;
  onClose: () => void;
  onSaved?: (p: Project) => void;
  onDeleted?: (id: string) => void;
}) {
  const [title, setTitle] = useState(project.title || "");
  const [idea, setIdea] = useState(project.idea || "");
  const [aspect, setAspect] = useState(project.aspect || "16:9");
  const [duration, setDuration] = useState(project.target_duration || 60);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);

  // Reset local state if a different project is opened.
  useEffect(() => {
    setTitle(project.title || "");
    setIdea(project.idea || "");
    setAspect(project.aspect || "16:9");
    setDuration(project.target_duration || 60);
    setErr("");
    setConfirmDelete(false);
  }, [project.id]);

  async function save() {
    setBusy(true);
    setErr("");
    try {
      const updated = await api.updateProject(project.id, {
        title: title.trim(),
        idea: idea.trim(),
        aspect,
        target_duration: Number(duration) || 60,
      });
      onSaved?.(updated);
      onClose();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    setErr("");
    try {
      await api.deleteProject(project.id);
      onDeleted?.(project.id);
      onClose();
    } catch (e) {
      setErr(String(e));
      setBusy(false);
    }
  }

  return (
    <Modal open title={`Edit · ${project.title || project.idea}`} onClose={onClose}>
      <div className="space-y-3">
        <label className="block text-sm">
          <span className="text-muted">title</span>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="mt-1 w-full bg-surface2 border border-edge rounded-lg px-3 py-1.5 text-sm outline-none focus:border-primary"
          />
        </label>
        <label className="block text-sm">
          <span className="text-muted">idea / thesis</span>
          <textarea
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            rows={3}
            className="mt-1 w-full bg-surface2 border border-edge rounded-lg px-3 py-2 text-sm outline-none focus:border-primary resize-none"
          />
        </label>
        <div className="flex gap-3">
          <label className="flex-1 text-sm">
            <span className="text-muted">aspect</span>
            <select
              value={aspect}
              onChange={(e) => setAspect(e.target.value)}
              className="mt-1 w-full bg-surface2 border border-edge rounded-lg px-3 py-1.5 text-sm outline-none focus:border-primary"
            >
              {["16:9", "9:16", "1:1", "4:5"].map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </label>
          <label className="w-28 text-sm">
            <span className="text-muted">length (s)</span>
            <input
              type="number"
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              className="mt-1 w-full bg-surface2 border border-edge rounded-lg px-2 py-1.5 text-sm outline-none focus:border-primary"
            />
          </label>
        </div>

        {err && <p className="text-danger text-xs">{err}</p>}

        <div className="flex items-center gap-2 pt-1">
          <Button onClick={save} disabled={busy} loading={busy}>
            Save
          </Button>
          {!confirmDelete ? (
            <Button variant="ghost" className="ml-auto" onClick={() => setConfirmDelete(true)}>
              Delete
            </Button>
          ) : (
            <span className="ml-auto flex items-center gap-2">
              <span className="text-xs text-muted">delete permanently?</span>
              <Button variant="ghost" onClick={() => setConfirmDelete(false)}>
                Cancel
              </Button>
              <Button variant="danger" onClick={remove} disabled={busy}>
                Delete
              </Button>
            </span>
          )}
        </div>
      </div>
    </Modal>
  );
}
