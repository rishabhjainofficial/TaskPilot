"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Sparkles, MessageSquare, Users, Plus, X, Trash2, FileText, LayoutGrid, List, Lock } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { AIChatPanel } from "@/components/ai-chat-panel";
import { TaskDetailModal } from "@/components/task-detail-modal";
import { DocumentPlanModal } from "@/components/document-plan-modal";

export default function ProjectBoardPage() {
  const params = useParams();
  const projectId = params.id as string;
  const queryClient = useQueryClient();

  const [aiPanelOpen, setAiPanelOpen] = useState(false);
  const [showTaskModal, setShowTaskModal] = useState(false);
  const [showDocPlanModal, setShowDocPlanModal] = useState(false);
  const [viewMode, setViewMode] = useState<"list" | "kanban">("list");
  const [activeDetailTask, setActiveDetailTask] = useState<any | null>(null);
  const [showAssignTeamModal, setShowAssignTeamModal] = useState(false);
  const [selectedAssignTeamId, setSelectedAssignTeamId] = useState("");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDesc, setTaskDesc] = useState("");
  const [taskPriority, setTaskPriority] = useState("medium");
  const [subtasksInput, setSubtasksInput] = useState("");
  const [errorToast, setErrorToast] = useState("");

  const triggerError = (msg: string) => {
    setErrorToast(msg);
    setTimeout(() => setErrorToast(""), 4000);
  };

  const { data: project } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => apiFetch<any>(`/projects/${projectId}`),
  });

  const { data: assignments = [] } = useQuery({
    queryKey: ["project-assignments", projectId],
    queryFn: () => apiFetch<any[]>(`/projects/${projectId}/assignments`).catch(() => []),
  });

  const { data: allTeams = [] } = useQuery({
    queryKey: ["teams"],
    queryFn: () => apiFetch<any[]>("/teams").catch(() => []),
  });

  const { data: tasks = [], isLoading } = useQuery({
    queryKey: ["tasks", projectId],
    queryFn: () => apiFetch<any[]>(`/projects/${projectId}/tasks`),
  });

  const assignTeamMutation = useMutation({
    mutationFn: (teamId: string) =>
      apiFetch(`/projects/${projectId}/assign`, {
        method: "POST",
        body: JSON.stringify({ team_id: teamId }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project-assignments", projectId] });
      setShowAssignTeamModal(false);
      setSelectedAssignTeamId("");
    },
    onError: (err: any) => {
      triggerError(err.message || "Failed to assign team");
    },
  });

  const removeAssignmentMutation = useMutation({
    mutationFn: (assignmentId: string) =>
      apiFetch(`/projects/${projectId}/assignments/${assignmentId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project-assignments", projectId] });
    },
    onError: (err: any) => {
      triggerError(err.message || "Failed to remove assignment");
    },
  });

  const createTaskMutation = useMutation({
    mutationFn: (body: any) =>
      apiFetch(`/projects/${projectId}/tasks`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
      setShowTaskModal(false);
      setTaskTitle("");
      setTaskDesc("");
      setSubtasksInput("");
    },
    onError: (err: any) => {
      triggerError(err.message || "Failed to create task");
    },
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ taskId, status }: { taskId: string; status: string }) =>
      apiFetch(`/tasks/${taskId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
    },
    onError: (err: any) => {
      triggerError(err.message || "Failed to update status");
    },
  });

  const addSubtaskMutation = useMutation({
    mutationFn: ({ taskId, title }: { taskId: string; title: string }) =>
      apiFetch(`/tasks/${taskId}/subtasks`, {
        method: "POST",
        body: JSON.stringify({ title }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
    },
  });

  const deleteTaskMutation = useMutation({
    mutationFn: (taskId: string) =>
      apiFetch(`/tasks/${taskId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
    },
  });

  const handleCreateTask = (e: React.FormEvent) => {
    e.preventDefault();
    const subtaskLines = subtasksInput
      .split("\n")
      .map((s) => s.trim())
      .filter((s) => s.length > 0)
      .map((title) => ({ title }));

    createTaskMutation.mutate({
      title: taskTitle,
      description: taskDesc,
      priority: taskPriority,
      subtasks: subtaskLines,
    });
  };

  const handleToggleTask = (task: any) => {
    const hasIncompleteSubtasks = task.subtasks?.some((st: any) => st.status !== "done");

    // Guardrail validation check on client before server rejects
    if (task.status !== "done" && hasIncompleteSubtasks) {
      triggerError(`🔒 Cannot mark "${task.title}" as complete while incomplete subtasks remain!`);
      return;
    }

    const nextStatus = task.status === "done" ? "todo" : "done";
    updateStatusMutation.mutate({ taskId: task.id, status: nextStatus });
  };

  const handleToggleSubtask = (st: any) => {
    const nextStatus = st.status === "done" ? "todo" : "done";
    updateStatusMutation.mutate({ taskId: st.id, status: nextStatus });
  };

  return (
    <div className="space-y-6">
      {/* Toast Alert */}
      {errorToast && (
        <div className="fixed top-4 right-4 z-50 rounded-lg bg-red-600 px-4 py-3 text-sm font-medium text-white shadow-lg animate-bounce">
          {errorToast}
        </div>
      )}

      {/* Breadcrumb & Header */}
      <div className="flex flex-col gap-2 border-b border-slate-200 pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 uppercase">
            <Link href="/dashboard" className="hover:text-blue-600">
              Projects
            </Link>
            <span>/</span>
            <span className="text-blue-600 font-bold">{project?.key}</span>
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">
            {project?.name || "Project Tasks"}
          </h1>
        </div>

        <div className="flex items-center gap-2">
          {/* View Mode Switcher */}
          <div className="flex items-center rounded-lg border border-slate-200 bg-white p-0.5">
            <button
              onClick={() => setViewMode("list")}
              className={`flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-semibold transition ${
                viewMode === "list" ? "bg-slate-100 text-slate-900" : "text-slate-500 hover:text-slate-800"
              }`}
            >
              <List className="h-3.5 w-3.5" /> List
            </button>
            <button
              onClick={() => setViewMode("kanban")}
              className={`flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-semibold transition ${
                viewMode === "kanban" ? "bg-slate-100 text-slate-900" : "text-slate-500 hover:text-slate-800"
              }`}
            >
              <LayoutGrid className="h-3.5 w-3.5" /> Board
            </button>
          </div>

          <button
            onClick={() => setShowDocPlanModal(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-50 border border-emerald-200 px-3.5 py-2 text-xs font-semibold text-emerald-800 shadow-xs hover:bg-emerald-100 transition-colors"
          >
            <FileText className="h-3.5 w-3.5 text-emerald-600" />
            Doc-to-Plan AI
          </button>
          <button
            onClick={() => setAiPanelOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-50 border border-indigo-200 px-3.5 py-2 text-xs font-semibold text-indigo-700 shadow-xs hover:bg-indigo-100 transition-colors"
          >
            <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
            AI Assistant
          </button>
          <button
            onClick={() => setShowTaskModal(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-blue-700"
          >
            <span>+</span> Add Task
          </button>
        </div>
      </div>

      {/* Assigned Teams Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-slate-100/70 p-3 border border-slate-200">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
            <Users className="h-4 w-4 text-blue-600" />
            <span>Assigned Teams:</span>
          </div>

          {assignments.filter((a: any) => a.team_id).length === 0 ? (
            <span className="text-xs text-slate-400 italic">No team assigned yet</span>
          ) : (
            assignments
              .filter((a: any) => a.team_id)
              .map((a: any) => (
                <span
                  key={a.id}
                  className="inline-flex items-center gap-1.5 rounded-md bg-white border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-800 shadow-2xs"
                >
                  <span className="font-semibold text-blue-700">👥 {a.team_name || "Team"}</span>
                  <button
                    onClick={() => removeAssignmentMutation.mutate(a.id)}
                    className="text-slate-400 hover:text-red-600 ml-1"
                    title="Unassign team"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))
          )}
        </div>

        <button
          onClick={() => setShowAssignTeamModal(true)}
          className="inline-flex items-center gap-1 rounded-md bg-white border border-slate-300 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition"
        >
          <Plus className="h-3 w-3" /> Assign Team
        </button>
      </div>

      {/* Task List */}
      {isLoading ? (
        <div className="py-12 text-center text-sm text-slate-500 animate-pulse">Loading tasks...</div>
      ) : tasks.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center">
          <div className="text-3xl mb-2">📋</div>
          <h3 className="text-base font-semibold text-slate-900">No tasks in this project</h3>
          <p className="mt-1 text-sm text-slate-500">Create your first task or break it down into subtasks.</p>
          <div className="mt-4 flex items-center justify-center gap-2">
            <button
              onClick={() => setAiPanelOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-50 border border-indigo-200 px-3.5 py-1.5 text-xs font-semibold text-indigo-700 hover:bg-indigo-100"
            >
              <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
              Ask AI to Propose Tasks
            </button>
            <button
              onClick={() => setShowTaskModal(true)}
              className="rounded-lg bg-blue-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
            >
              Create Manually
            </button>
          </div>
        </div>
      ) : viewMode === "list" ? (
        <div className="space-y-3">
          {tasks.map((task: any) => {
            const hasSubtasks = task.subtasks && task.subtasks.length > 0;
            const completedSubtasks = task.subtasks?.filter((st: any) => st.status === "done").length || 0;
            const hasIncomplete = task.subtasks?.some((st: any) => st.status !== "done");

            return (
              <div
                key={task.id}
                className={`rounded-xl border bg-white p-4 shadow-xs transition ${
                  task.status === "done" ? "border-slate-200 bg-slate-50/50" : "border-slate-200"
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3 flex-1">
                    <button
                      onClick={() => handleToggleTask(task)}
                      className={`mt-0.5 text-lg transition ${
                        hasSubtasks && hasIncomplete && task.status !== "done"
                          ? "cursor-not-allowed opacity-60"
                          : "hover:scale-110"
                      }`}
                      title={
                        hasSubtasks && hasIncomplete && task.status !== "done"
                          ? "Complete all subtasks first"
                          : "Toggle task"
                      }
                    >
                      {task.status === "done" ? "✅" : hasSubtasks && hasIncomplete ? "🔒" : "⬜"}
                    </button>

                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-slate-400">
                          {task.task_code}
                        </span>
                        <h4
                          onClick={() => setActiveDetailTask(task)}
                          className={`text-sm font-semibold text-slate-900 cursor-pointer hover:text-blue-600 ${
                            task.status === "done" ? "line-through text-slate-400" : ""
                          }`}
                        >
                          {task.title}
                        </h4>
                        <span
                          className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                            task.priority === "critical"
                              ? "bg-red-100 text-red-700"
                              : task.priority === "high"
                              ? "bg-amber-100 text-amber-700"
                              : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {task.priority}
                        </span>
                        <button
                          onClick={() => setActiveDetailTask(task)}
                          className="flex items-center gap-1 rounded bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600 hover:bg-blue-50 hover:text-blue-700"
                        >
                          <MessageSquare className="h-3 w-3" />
                          Details
                        </button>
                      </div>

                      {task.description && (
                        <p className="mt-1 text-xs text-slate-500">{task.description}</p>
                      )}

                      {/* Subtasks Progress */}
                      {hasSubtasks && (
                        <div className="mt-3 pl-2 border-l-2 border-slate-200 space-y-1.5">
                          <div className="text-[11px] font-semibold text-slate-500">
                            Subtasks ({completedSubtasks}/{task.subtasks.length}):
                          </div>
                          {task.subtasks.map((st: any) => (
                            <div
                              key={st.id}
                              onClick={() => handleToggleSubtask(st)}
                              className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer hover:text-blue-600"
                            >
                              <span>{st.status === "done" ? "✅" : "⬜"}</span>
                              <span className={st.status === "done" ? "line-through text-slate-400" : ""}>
                                {st.title}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  <button
                    onClick={() => deleteTaskMutation.mutate(task.id)}
                    className="text-xs text-slate-400 hover:text-red-600 p-1"
                    title="Delete task"
                  >
                    🗑️
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* Kanban Board View */
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-start">
          {[
            { id: "todo", title: "To Do", bg: "bg-slate-100/70", border: "border-slate-200", badge: "bg-slate-200 text-slate-700" },
            { id: "in_progress", title: "In Progress", bg: "bg-blue-50/50", border: "border-blue-200", badge: "bg-blue-100 text-blue-700" },
            { id: "in_review", title: "Review", bg: "bg-purple-50/50", border: "border-purple-200", badge: "bg-purple-100 text-purple-700" },
            { id: "done", title: "Completed", bg: "bg-emerald-50/50", border: "border-emerald-200", badge: "bg-emerald-100 text-emerald-700" },
          ].map((col) => {
            const colTasks = tasks.filter((t: any) => (t.status || "todo") === col.id);
            return (
              <div key={col.id} className={`rounded-2xl border ${col.border} ${col.bg} p-3.5 space-y-3 min-h-[500px] flex flex-col`}>
                <div className="flex items-center justify-between pb-2 border-b border-slate-200/60">
                  <span className="text-xs font-bold text-slate-800">{col.title}</span>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${col.badge}`}>
                    {colTasks.length}
                  </span>
                </div>

                <div className="space-y-2.5 flex-1 overflow-y-auto">
                  {colTasks.length === 0 ? (
                    <div className="text-center py-8 text-[11px] text-slate-400 italic">No tasks</div>
                  ) : (
                    colTasks.map((t: any) => (
                      <div
                        key={t.id}
                        className="rounded-xl border border-slate-200 bg-white p-3 shadow-2xs hover:shadow-xs transition cursor-pointer space-y-2"
                        onClick={() => setActiveDetailTask(t)}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[10px] font-bold text-slate-400">{t.task_code}</span>
                          <span className={`rounded px-1.5 py-0.2 text-[9px] font-bold uppercase ${
                            t.priority === "critical" ? "bg-red-100 text-red-700" : t.priority === "high" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-600"
                          }`}>
                            {t.priority}
                          </span>
                        </div>
                        <h4 className="text-xs font-bold text-slate-900 line-clamp-2 hover:text-blue-600">{t.title}</h4>
                        {t.description && <p className="text-[11px] text-slate-500 line-clamp-2">{t.description}</p>}

                        <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[10px] text-slate-500">
                          {t.subtasks?.length > 0 && <span>📋 {t.subtasks.filter((st: any) => st.status === "done").length}/{t.subtasks.length}</span>}
                          <select
                            value={t.status || "todo"}
                            onClick={(e) => e.stopPropagation()}
                            onChange={(e) => updateStatusMutation.mutate({ taskId: t.id, status: e.target.value })}
                            className="bg-transparent border border-slate-200 rounded px-1.5 py-0.5 text-[10px] font-semibold text-slate-700 cursor-pointer"
                          >
                            <option value="todo">To Do</option>
                            <option value="in_progress">In Progress</option>
                            <option value="in_review">Review</option>
                            <option value="done">Done</option>
                          </select>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Create Task Modal */}
      {showTaskModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-xs">
          <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
            <h3 className="text-lg font-bold text-slate-900">Create Task in {project?.key}</h3>

            <form onSubmit={handleCreateTask} className="mt-4 space-y-3.5">
              <div>
                <label className="block text-xs font-semibold text-slate-700">Task Title</label>
                <input
                  type="text"
                  required
                  value={taskTitle}
                  onChange={(e) => setTaskTitle(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm outline-none focus:border-blue-500"
                  placeholder="e.g. Conduct daily morning room inspection"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700">Description</label>
                <textarea
                  rows={2}
                  value={taskDesc}
                  onChange={(e) => setTaskDesc(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm outline-none focus:border-blue-500"
                  placeholder="Task context or instructions"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700">Priority</label>
                <select
                  value={taskPriority}
                  onChange={(e) => setTaskPriority(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm outline-none"
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700">
                  Subtasks (Optional, one per line)
                </label>
                <textarea
                  rows={3}
                  value={subtasksInput}
                  onChange={(e) => setSubtasksInput(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-xs font-mono outline-none focus:border-blue-500"
                  placeholder={"Check mini-bar\nInspect bed linen\nVerify bathroom toiletries"}
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowTaskModal(false)}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createTaskMutation.isPending}
                  className="rounded-lg bg-blue-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:bg-blue-300"
                >
                  {createTaskMutation.isPending ? "Creating..." : "Save Task"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {/* Assign Team Modal */}
      {showAssignTeamModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-sm rounded-2xl bg-white p-5 shadow-xl border border-slate-200">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="text-sm font-bold text-slate-900">Assign Team to Project</h3>
              <button
                onClick={() => setShowAssignTeamModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <p className="mt-2 text-xs text-slate-500">
              Assigning a team grants the designated Team Lead management rights and enables AI role-based matching.
            </p>

            <div className="mt-3">
              <label className="block text-xs font-semibold text-slate-700 mb-1">Select Team</label>
              <select
                value={selectedAssignTeamId}
                onChange={(e) => setSelectedAssignTeamId(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 focus:outline-none"
              >
                <option value="">Choose team...</option>
                {allTeams
                  .filter((t: any) => !assignments.some((a: any) => a.team_id === t.id))
                  .map((t: any) => (
                    <option key={t.id} value={t.id}>
                      {t.name} ({t.members_count || 0} members)
                    </option>
                  ))}
              </select>
            </div>

            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setShowAssignTeamModal(false)}
                className="rounded-md border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                disabled={!selectedAssignTeamId || assignTeamMutation.isPending}
                onClick={() => assignTeamMutation.mutate(selectedAssignTeamId)}
                className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {assignTeamMutation.isPending ? "Assigning..." : "Assign"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Task Detail Activity Modal (Comments, Time Logs, Attachments) */}
      {activeDetailTask && (
        <TaskDetailModal
          taskId={activeDetailTask.id}
          projectId={projectId}
          taskTitle={activeDetailTask.title}
          taskCode={activeDetailTask.task_code}
          onClose={() => setActiveDetailTask(null)}
        />
      )}

      {/* Document-to-Plan AI Modal */}
      {showDocPlanModal && (
        <DocumentPlanModal
          projectId={projectId}
          projectName={project?.name}
          onClose={() => setShowDocPlanModal(false)}
        />
      )}
      {/* AI Assistant Panel */}
      <AIChatPanel
        projectId={projectId}
        projectName={project?.name}
        isOpen={aiPanelOpen}
        onClose={() => setAiPanelOpen(false)}
      />
    </div>
  );
}
