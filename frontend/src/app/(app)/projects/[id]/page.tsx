"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { AIChatPanel } from "@/components/ai-chat-panel";

export default function ProjectBoardPage() {
  const params = useParams();
  const projectId = params.id as string;
  const queryClient = useQueryClient();

  const [aiPanelOpen, setAiPanelOpen] = useState(false);
  const [showTaskModal, setShowTaskModal] = useState(false);
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

  const { data: tasks = [], isLoading } = useQuery({
    queryKey: ["tasks", projectId],
    queryFn: () => apiFetch<any[]>(`/projects/${projectId}/tasks`),
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
      ) : (
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
                          className={`text-sm font-semibold text-slate-900 ${
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
