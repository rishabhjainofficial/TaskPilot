"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileText, Sparkles, Check, X, ArrowRight, UserCheck, AlertCircle } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface DocumentPlanModalProps {
  projectId: string;
  projectName?: string;
  onClose: () => void;
}

export function DocumentPlanModal({ projectId, projectName, onClose }: DocumentPlanModalProps) {
  const queryClient = useQueryClient();
  const [docText, setDocText] = useState("");
  const [filename, setFilename] = useState("Feature-Spec.md");
  const [autoApply, setAutoApply] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");
  const [generatedResult, setGeneratedResult] = useState<any | null>(null);

  const generateMutation = useMutation({
    mutationFn: (body: any) =>
      apiFetch(`/projects/${projectId}/documents/plan`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (data: any) => {
      setGeneratedResult(data);
      queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
      queryClient.invalidateQueries({ queryKey: ["subscription-usage"] });
    },
    onError: (err: any) => {
      setErrorMsg(err.message || "Failed to generate plan from document");
    },
  });

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setFilename(file.name);
      const reader = new FileReader();
      reader.onload = (event) => {
        const content = event.target?.result as string;
        setDocText(content || "");
      };
      reader.readAsText(file);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
      <div className="w-full max-w-2xl max-h-[90vh] flex flex-col rounded-2xl bg-white shadow-2xl border border-slate-200 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4 bg-slate-50">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-100 text-indigo-700 font-bold">
              <FileText className="h-4 w-4" />
            </span>
            <div>
              <h3 className="text-base font-bold text-slate-900">Document-to-Plan AI Generator</h3>
              <p className="text-xs text-slate-500">
                Transform PRDs, specifications, and user stories into actionable tasks matched to your team
              </p>
            </div>
          </div>
          <button onClick={onClose} className="rounded p-1 text-slate-400 hover:text-slate-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {errorMsg && (
            <div className="rounded-lg bg-red-50 p-3 text-xs text-red-700 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-red-500" />
              <span>{errorMsg}</span>
            </div>
          )}

          {!generatedResult ? (
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Upload Specification File (.md, .txt)</label>
                <input
                  type="file"
                  accept=".txt,.md,.markdown"
                  onChange={handleFileUpload}
                  className="block w-full text-xs text-slate-500 file:mr-4 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 cursor-pointer"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-xs font-bold text-slate-700">Or Paste Specification Text</label>
                  <span className="text-[11px] text-slate-400">Headings become tasks, bullets become subtasks</span>
                </div>
                <textarea
                  rows={8}
                  placeholder={`# Sprint 4 Architecture\n\n## Feature: Multi-Tenant Billing Engine\n- [ ] Create stripe webhook handler\n- [ ] Enforce seat and project quota limits\n\n## Feature: Kanban Board\n- [ ] Implement drag and drop columns\n- [ ] Lock blocked tasks`}
                  value={docText}
                  onChange={(e) => setDocText(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 p-3 text-xs font-mono text-slate-800 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="flex items-center gap-2 text-xs text-slate-700 bg-slate-50 p-3 rounded-xl border border-slate-200">
                <input
                  type="checkbox"
                  id="auto_apply"
                  checked={autoApply}
                  onChange={(e) => setAutoApply(e.target.checked)}
                  className="rounded text-indigo-600 cursor-pointer"
                />
                <label htmlFor="auto_apply" className="cursor-pointer font-medium">
                  Automatically create extracted tasks and subtasks immediately on this project board
                </label>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-4 text-xs text-emerald-800">
                <div className="font-bold text-sm">🎉 Plan Generated Successfully!</div>
                <p className="mt-1 text-emerald-700">
                  Extracted {generatedResult.tasks_count} tasks and matched candidate team members by specialization.
                </p>
              </div>

              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">Extracted Tasks</h4>
                <div className="divide-y divide-slate-100 border border-slate-200 rounded-xl overflow-hidden bg-white">
                  {generatedResult.tasks?.map((t: any, i: number) => (
                    <div key={i} className="p-3 text-xs space-y-1 hover:bg-slate-50">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-900">{t.title}</span>
                        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-slate-600">
                          {t.priority}
                        </span>
                      </div>
                      {t.description && <p className="text-slate-500 text-[11px]">{t.description}</p>}
                      <div className="flex items-center gap-3 pt-1 text-[11px] text-slate-500">
                        {t.subtasks?.length > 0 && <span>📋 {t.subtasks.length} subtasks</span>}
                        {t.assigned_user_name ? (
                          <span className="flex items-center gap-1 text-blue-700 font-semibold">
                            <UserCheck className="h-3 w-3" /> Assigned to: {t.assigned_user_name} ({t.recommended_role})
                          </span>
                        ) : (
                          <span className="text-slate-400 italic">Target role: {t.recommended_role}</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-slate-200 px-6 py-3 bg-slate-50 flex items-center justify-between">
          <button
            onClick={onClose}
            className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50"
          >
            {generatedResult ? "Close" : "Cancel"}
          </button>

          {!generatedResult && (
            <button
              disabled={!docText.trim() || generateMutation.isPending}
              onClick={() => {
                generateMutation.mutate({
                  document_text: docText,
                  filename,
                  auto_apply: autoApply,
                });
              }}
              className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-bold text-white hover:bg-indigo-700 disabled:opacity-50 shadow-xs"
            >
              <Sparkles className="h-3.5 w-3.5" />
              {generateMutation.isPending ? "Analyzing & Generating..." : "Generate Tasks with AI"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
