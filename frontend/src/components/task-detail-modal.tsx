"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { MessageSquare, Clock, Paperclip, X, CornerDownRight, Download, Trash2, Plus, GitFork, Lock } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface TaskDetailModalProps {
  taskId: string;
  projectId: string;
  taskTitle: string;
  taskCode?: string;
  onClose: () => void;
}

export function TaskDetailModal({ taskId, projectId, taskTitle, taskCode, onClose }: TaskDetailModalProps) {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"comments" | "attachments" | "timelogs" | "dependencies">("comments");
  const [selectedBlockingTaskId, setSelectedBlockingTaskId] = useState("");

  // Comments state
  const [newComment, setNewComment] = useState("");
  const [replyToId, setReplyToId] = useState<string | null>(null);

  // Time log state
  const [durationMinutes, setDurationMinutes] = useState<number>(30);
  const [timeDescription, setTimeDescription] = useState("");

  // Attachments state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  // 1. Fetch comments
  const { data: comments = [], isLoading: commentsLoading } = useQuery({
    queryKey: ["task-comments", taskId],
    queryFn: () => apiFetch<any[]>(`/tasks/${taskId}/comments`),
  });

  // 2. Fetch time logs
  const { data: timeLogsData, isLoading: timeLogsLoading } = useQuery({
    queryKey: ["task-time-logs", taskId],
    queryFn: () => apiFetch<any>(`/tasks/${taskId}/time-logs`),
  });

  // 3. Fetch attachments
  const { data: attachments = [], isLoading: attachmentsLoading } = useQuery({
    queryKey: ["task-attachments", taskId],
    queryFn: () => apiFetch<any[]>(`/tasks/${taskId}/attachments`),
  });

  // 4. Fetch dependencies
  const { data: dependencies, isLoading: depsLoading } = useQuery({
    queryKey: ["task-dependencies", taskId],
    queryFn: () => apiFetch<any>(`/tasks/${taskId}/dependencies`),
  });

  // 5. Fetch all project tasks (for dependency selector)
  const { data: allProjectTasks = [] } = useQuery({
    queryKey: ["tasks", projectId],
    queryFn: () => apiFetch<any[]>(`/projects/${projectId}/tasks`),
  });

  const addDependencyMutation = useMutation({
    mutationFn: (blockingTaskId: string) =>
      apiFetch(`/tasks/${taskId}/dependencies`, {
        method: "POST",
        body: JSON.stringify({ blocking_task_id: blockingTaskId }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["task-dependencies", taskId] });
      queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
      setSelectedBlockingTaskId("");
      setErrorMsg("");
    },
    onError: (err: any) => {
      setErrorMsg(err.message || "Failed to add dependency");
    },
  });

  const removeDependencyMutation = useMutation({
    mutationFn: (depId: string) =>
      apiFetch(`/tasks/${taskId}/dependencies/${depId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["task-dependencies", taskId] });
      queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
    },
    onError: (err: any) => {
      setErrorMsg(err.message || "Failed to remove dependency");
    },
  });

  // Add Comment Mutation
  const addCommentMutation = useMutation({
    mutationFn: (body: any) =>
      apiFetch(`/tasks/${taskId}/comments`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["task-comments", taskId] });
      setNewComment("");
      setReplyToId(null);
    },
    onError: (err: any) => setErrorMsg(err.message || "Failed to post comment"),
  });

  // Add Time Log Mutation
  const addTimeLogMutation = useMutation({
    mutationFn: (body: any) =>
      apiFetch(`/tasks/${taskId}/time-logs`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["task-time-logs", taskId] });
      setDurationMinutes(30);
      setTimeDescription("");
    },
    onError: (err: any) => setErrorMsg(err.message || "Failed to log time"),
  });

  // Attachment upload & confirm
  const handleFileUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;
    setUploading(true);
    setErrorMsg("");

    try {
      // 1. Request presigned upload URL
      const ticket: any = await apiFetch(`/tasks/${taskId}/attachments/upload-url`, {
        method: "POST",
        body: JSON.stringify({
          filename: selectedFile.name,
          content_type: selectedFile.type || "application/octet-stream",
          size_bytes: selectedFile.size,
        }),
      });

      // 2. Direct upload if valid http, or simulate
      try {
        if (ticket.upload_url && ticket.upload_url.startsWith("http")) {
          await fetch(ticket.upload_url, {
            method: "PUT",
            headers: { "Content-Type": selectedFile.type || "application/octet-stream" },
            body: selectedFile,
          });
        }
      } catch (uploadErr) {
        // Continue to confirmation
      }

      // 3. Confirm attachment in database
      await apiFetch(`/tasks/${taskId}/attachments/confirm`, {
        method: "POST",
        body: JSON.stringify({
          storage_key: ticket.storage_key,
          filename: selectedFile.name,
          content_type: selectedFile.type || "application/octet-stream",
          size_bytes: selectedFile.size,
        }),
      });

      queryClient.invalidateQueries({ queryKey: ["task-attachments", taskId] });
      setSelectedFile(null);
    } catch (err: any) {
      setErrorMsg(err.message || "Attachment upload failed");
    } finally {
      setUploading(false);
    }
  };

  const downloadAttachment = async (attId: string, filename: string) => {
    try {
      const res: any = await apiFetch(`/tasks/${taskId}/attachments/${attId}/download`);
      if (res?.download_url) {
        window.open(res.download_url, "_blank");
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to get download URL");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
      <div className="w-full max-w-2xl rounded-2xl bg-white shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4 bg-slate-50">
          <div>
            <div className="flex items-center gap-2">
              {taskCode && <span className="font-mono text-xs font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded">{taskCode}</span>}
              <h2 className="text-base font-bold text-slate-900">{taskTitle}</h2>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">Task Collaboration & Activity</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-200 hover:text-slate-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Tab Bar */}
        <div className="flex border-b border-slate-200 px-6 bg-white gap-6">
          <button
            onClick={() => setActiveTab("comments")}
            className={`flex items-center gap-2 py-3 text-xs font-semibold border-b-2 transition-colors ${
              activeTab === "comments" ? "border-blue-600 text-blue-600" : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <MessageSquare className="h-4 w-4" />
            Comments ({comments.length})
          </button>
          <button
            onClick={() => setActiveTab("timelogs")}
            className={`flex items-center gap-2 py-3 text-xs font-semibold border-b-2 transition-colors ${
              activeTab === "timelogs" ? "border-blue-600 text-blue-600" : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Clock className="h-4 w-4" />
            Time Logs ({timeLogsData?.total_duration_minutes || 0}m)
          </button>
          <button
            onClick={() => setActiveTab("attachments")}
            className={`flex items-center gap-2 py-3 text-xs font-semibold border-b-2 transition-colors ${
              activeTab === "attachments" ? "border-blue-600 text-blue-600" : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Paperclip className="h-4 w-4" />
            Attachments ({attachments.length})
          </button>
          <button
            onClick={() => setActiveTab("dependencies")}
            className={`flex items-center gap-2 py-3 text-xs font-semibold border-b-2 transition-colors ${
              activeTab === "dependencies" ? "border-blue-600 text-blue-600" : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <GitFork className="h-4 w-4" />
            Dependencies ({dependencies?.blocked_by?.length || 0})
          </button>
        </div>

        {errorMsg && (
          <div className="bg-red-50 text-red-700 px-6 py-2 text-xs font-medium border-b border-red-200 flex justify-between items-center">
            <span>{errorMsg}</span>
            <button onClick={() => setErrorMsg("")} className="text-red-500 font-bold ml-2">✕</button>
          </div>
        )}

        {/* Content Area */}
        <div className="p-6 overflow-y-auto flex-1 space-y-4">
          {/* TAB 1: COMMENTS */}
          {activeTab === "comments" && (
            <div className="space-y-4">
              <div className="space-y-3">
                {comments.length === 0 ? (
                  <div className="text-center py-8 text-xs text-slate-400">No comments yet. Start the conversation below.</div>
                ) : (
                  comments.map((c: any) => (
                    <div key={c.id} className="rounded-xl border border-slate-200 p-3.5 bg-slate-50/50 space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-bold text-slate-800">{c.user_full_name} <span className="font-normal text-slate-400">({c.user_email})</span></span>
                        <span className="text-slate-400 text-[11px]">{new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      </div>
                      <p className="text-xs text-slate-700 whitespace-pre-wrap">{c.content}</p>
                      
                      <div className="flex justify-end pt-1">
                        <button
                          onClick={() => setReplyToId(c.id)}
                          className="flex items-center gap-1 text-[11px] font-semibold text-blue-600 hover:underline"
                        >
                          <CornerDownRight className="h-3 w-3" /> Reply
                        </button>
                      </div>

                      {/* Nested Replies */}
                      {c.replies?.length > 0 && (
                        <div className="pl-4 mt-2 border-l-2 border-blue-200 space-y-2">
                          {c.replies.map((r: any) => (
                            <div key={r.id} className="bg-white rounded-lg p-2.5 border border-slate-100 text-xs space-y-1">
                              <div className="flex justify-between items-center text-[11px]">
                                <span className="font-bold text-slate-800">{r.user_full_name}</span>
                                <span className="text-slate-400">{new Date(r.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                              </div>
                              <p className="text-slate-700 text-xs">{r.content}</p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>

              {/* Add Comment Input */}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (!newComment.trim()) return;
                  addCommentMutation.mutate({ content: newComment, parent_comment_id: replyToId });
                }}
                className="pt-2 border-t border-slate-200 space-y-2"
              >
                {replyToId && (
                  <div className="flex items-center justify-between text-xs bg-blue-50 text-blue-700 px-3 py-1 rounded-md">
                    <span>Replying to comment...</span>
                    <button type="button" onClick={() => setReplyToId(null)} className="font-bold text-blue-800">Cancel</button>
                  </div>
                )}
                <textarea
                  rows={2}
                  value={newComment}
                  onChange={(e) => setNewComment(e.target.value)}
                  placeholder="Write a comment or update..."
                  className="w-full rounded-xl border border-slate-300 p-2.5 text-xs outline-none focus:border-blue-500"
                />
                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={addCommentMutation.isPending || !newComment.trim()}
                    className="rounded-lg bg-blue-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    {addCommentMutation.isPending ? "Posting..." : "Post Comment"}
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* TAB 2: TIME LOGS */}
          {activeTab === "timelogs" && (
            <div className="space-y-4">
              <div className="rounded-xl bg-blue-50/70 border border-blue-100 p-4 flex justify-between items-center">
                <div>
                  <span className="text-xs text-blue-800 font-medium">Total Time Tracked</span>
                  <div className="text-xl font-bold text-blue-900 mt-0.5">
                    {Math.floor((timeLogsData?.total_duration_minutes || 0) / 60)}h {(timeLogsData?.total_duration_minutes || 0) % 60}m
                  </div>
                </div>
                <Clock className="h-8 w-8 text-blue-300" />
              </div>

              {/* Log History */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">Logged Entries</h4>
                {timeLogsData?.logs?.length === 0 ? (
                  <div className="text-center py-6 text-xs text-slate-400">No time recorded on this task yet.</div>
                ) : (
                  timeLogsData?.logs?.map((l: any) => (
                    <div key={l.id} className="flex items-center justify-between p-3 rounded-lg border border-slate-200 bg-white text-xs">
                      <div>
                        <div className="font-semibold text-slate-800">{l.user_full_name}</div>
                        <div className="text-slate-500 text-[11px]">{l.description || "Work session"} • {l.log_date}</div>
                      </div>
                      <span className="font-mono font-bold text-blue-700 bg-blue-50 px-2 py-1 rounded">
                        {l.duration_minutes} min
                      </span>
                    </div>
                  ))
                )}
              </div>

              {/* Add Time Form */}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  addTimeLogMutation.mutate({ duration_minutes: Number(durationMinutes), description: timeDescription });
                }}
                className="pt-3 border-t border-slate-200 space-y-3"
              >
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Duration (Minutes)</label>
                    <input
                      type="number"
                      min={1}
                      value={durationMinutes}
                      onChange={(e) => setDurationMinutes(Number(e.target.value))}
                      className="w-full rounded-lg border border-slate-300 p-2 text-xs outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Work Note</label>
                    <input
                      type="text"
                      value={timeDescription}
                      onChange={(e) => setTimeDescription(e.target.value)}
                      placeholder="e.g. Bugfix & Unit tests"
                      className="w-full rounded-lg border border-slate-300 p-2 text-xs outline-none focus:border-blue-500"
                    />
                  </div>
                </div>
                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={addTimeLogMutation.isPending || durationMinutes <= 0}
                    className="rounded-lg bg-blue-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    {addTimeLogMutation.isPending ? "Logging..." : "Log Time"}
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* TAB 3: ATTACHMENTS */}
          {activeTab === "attachments" && (
            <div className="space-y-4">
              <div className="space-y-2">
                {attachments.length === 0 ? (
                  <div className="text-center py-8 text-xs text-slate-400">No files attached to this task.</div>
                ) : (
                  attachments.map((a: any) => (
                    <div key={a.id} className="flex items-center justify-between p-3 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 transition-colors">
                      <div className="flex items-center gap-3">
                        <div className="p-2 bg-blue-50 text-blue-700 rounded-lg">
                          <Paperclip className="h-4 w-4" />
                        </div>
                        <div>
                          <div className="text-xs font-semibold text-slate-800">{a.filename}</div>
                          <div className="text-[11px] text-slate-400">
                            {(a.size_bytes / 1024).toFixed(1)} KB • {a.user_full_name}
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={() => downloadAttachment(a.id, a.filename)}
                        className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
                      >
                        <Download className="h-3.5 w-3.5" /> Download
                      </button>
                    </div>
                  ))
                )}
              </div>

              {/* Upload Input */}
              <form onSubmit={handleFileUpload} className="pt-3 border-t border-slate-200 space-y-3">
                <label className="block text-xs font-semibold text-slate-700">Attach Deliverable or Screenshot (Max 25MB)</label>
                <input
                  type="file"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className="block w-full text-xs text-slate-500 file:mr-4 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer"
                />
                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={uploading || !selectedFile}
                    className="rounded-lg bg-blue-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    {uploading ? "Uploading to S3..." : "Upload File"}
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* Dependencies Tab */}
          {activeTab === "dependencies" && (
            <div className="space-y-5">
              {/* Add Dependency Form */}
              <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-3">
                <div className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                  <Plus className="h-4 w-4 text-blue-600" /> Add Blocking Dependency
                </div>
                <p className="text-[11px] text-slate-500">
                  Select a task that must be completed before this task can be started or marked done.
                </p>
                <div className="flex gap-2">
                  <select
                    value={selectedBlockingTaskId}
                    onChange={(e) => setSelectedBlockingTaskId(e.target.value)}
                    className="flex-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-800 focus:outline-none"
                  >
                    <option value="">Choose blocking task...</option>
                    {allProjectTasks
                      .filter(
                        (t: any) =>
                          t.id !== taskId &&
                          !dependencies?.blocked_by?.some((dep: any) => dep.task_id === t.id)
                      )
                      .map((t: any) => (
                        <option key={t.id} value={t.id}>
                          {t.task_code}: {t.title} ({t.status})
                        </option>
                      ))}
                  </select>
                  <button
                    disabled={!selectedBlockingTaskId || addDependencyMutation.isPending}
                    onClick={() => addDependencyMutation.mutate(selectedBlockingTaskId)}
                    className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    {addDependencyMutation.isPending ? "Adding..." : "Add"}
                  </button>
                </div>
              </div>

              {/* Blocked By List */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                  <Lock className="h-3.5 w-3.5 text-amber-500" /> Blocked By (Must Finish First)
                </h4>
                {depsLoading ? (
                  <div className="text-xs text-slate-400 py-3">Loading dependencies...</div>
                ) : !dependencies?.blocked_by || dependencies.blocked_by.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-slate-200 p-4 text-center text-xs text-slate-400">
                    No blocking dependencies. This task can be started freely.
                  </div>
                ) : (
                  <div className="divide-y divide-slate-100 border border-slate-200 rounded-xl overflow-hidden bg-white">
                    {dependencies.blocked_by.map((dep: any) => (
                      <div key={dep.id} className="flex items-center justify-between p-3 text-xs">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-slate-500">{dep.task_code}</span>
                          <span className="font-semibold text-slate-800">{dep.title}</span>
                          <span
                            className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                              dep.status === "done" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
                            }`}
                          >
                            {dep.status}
                          </span>
                        </div>
                        <button
                          onClick={() => removeDependencyMutation.mutate(dep.id)}
                          className="text-slate-400 hover:text-red-600 p-1"
                          title="Remove dependency"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Blocking List */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  Blocking (Waiting on this task)
                </h4>
                {!dependencies?.blocking || dependencies.blocking.length === 0 ? (
                  <div className="text-xs text-slate-400 italic">No other tasks are waiting on this task.</div>
                ) : (
                  <div className="divide-y divide-slate-100 border border-slate-200 rounded-xl overflow-hidden bg-white">
                    {dependencies.blocking.map((dep: any) => (
                      <div key={dep.id} className="flex items-center justify-between p-3 text-xs">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-slate-500">{dep.task_code}</span>
                          <span className="font-semibold text-slate-800">{dep.title}</span>
                          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-slate-600">
                            {dep.status}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

