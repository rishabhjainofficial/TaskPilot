"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [name, setName] = useState("");
  const [key, setKey] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");

  const { data: profile } = useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<any>("/me"),
  });

  const { data: projects = [], isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: () => apiFetch<any[]>("/projects"),
  });

  const createProjectMutation = useMutation({
    mutationFn: (newProj: any) =>
      apiFetch("/projects", {
        method: "POST",
        body: JSON.stringify(newProj),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setShowCreateModal(false);
      setName("");
      setKey("");
      setDescription("");
      setError("");
    },
    onError: (err: any) => {
      setError(err.message || "Failed to create project");
    },
  });

  const canCreateProject =
    profile?.current_role === "owner" ||
    profile?.current_role === "admin" ||
    profile?.current_role === "manager" ||
    profile?.permissions?.includes("project.create");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    createProjectMutation.mutate({ name, key: key.toUpperCase(), description });
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Projects</h1>
          <p className="mt-1 text-sm text-slate-500">
            Select a project to manage tasks and view AI planning
          </p>
        </div>

        {canCreateProject && (
          <button
            onClick={() => setShowCreateModal(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-xs hover:bg-blue-700 transition"
          >
            <span>+</span> New Project
          </button>
        )}
      </div>

      {/* Projects Grid */}
      {isLoading ? (
        <div className="py-12 text-center text-sm text-slate-500 animate-pulse">Loading projects...</div>
      ) : projects.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center">
          <div className="text-3xl mb-2">📁</div>
          <h3 className="text-base font-semibold text-slate-900">No projects yet</h3>
          <p className="mt-1 text-sm text-slate-500">Get started by creating your first team project.</p>
          {canCreateProject && (
            <button
              onClick={() => setShowCreateModal(true)}
              className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Create Project
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <Link
              key={p.id}
              href={`/projects/${p.id}`}
              className="group rounded-xl border border-slate-200 bg-white p-5 shadow-xs transition hover:border-blue-400 hover:shadow-md"
            >
              <div className="flex items-center justify-between">
                <span className="rounded bg-blue-50 px-2 py-0.5 text-xs font-bold text-blue-700">
                  {p.key}
                </span>
                <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">
                  {p.status}
                </span>
              </div>
              <h3 className="mt-3 text-base font-semibold text-slate-900 group-hover:text-blue-600">
                {p.name}
              </h3>
              {p.description && (
                <p className="mt-1 line-clamp-2 text-xs text-slate-500">{p.description}</p>
              )}
            </Link>
          ))}
        </div>
      )}

      {/* Create Project Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-xs">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h3 className="text-lg font-bold text-slate-900">Create New Project</h3>
            <p className="mt-1 text-xs text-slate-500">
              Each project has a short key (like &quot;OPS&quot; or &quot;APP&quot;) used for task numbering.
            </p>

            {error && (
              <div className="mt-4 rounded-lg bg-red-50 p-3 text-xs text-red-700 border border-red-200">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700">Project Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm outline-none focus:border-blue-500"
                  placeholder="Daily Operations Checklist"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700">Project Key (2-6 letters)</label>
                <input
                  type="text"
                  required
                  maxLength={6}
                  value={key}
                  onChange={(e) => setKey(e.target.value.toUpperCase())}
                  className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm uppercase tracking-wider outline-none focus:border-blue-500"
                  placeholder="OPS"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700">Description (Optional)</label>
                <textarea
                  rows={2}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm outline-none focus:border-blue-500"
                  placeholder="Operational SOPs and daily team checklists"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createProjectMutation.isPending}
                  className="rounded-lg bg-blue-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:bg-blue-300"
                >
                  {createProjectMutation.isPending ? "Creating..." : "Create Project"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
