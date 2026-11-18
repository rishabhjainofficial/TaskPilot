"use client";

import { useState, useRef, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Sparkles,
  Send,
  X,
  CheckCircle2,
  XCircle,
  Clock,
  ArrowRight,
  ShieldCheck,
  Bot,
  User as UserIcon,
  AlertTriangle,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

interface ActionItem {
  tool: string;
  args: Record<string, any>;
}

interface Proposal {
  id: string;
  conversation_id: string;
  project_id: string;
  explanation: string;
  actions: ActionItem[];
  status: "pending" | "confirmed" | "rejected" | "expired";
  created_at: string;
  expires_at: string;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  proposal?: Proposal | null;
  read_results?: any[] | null;
  timestamp: string;
}

interface AIChatPanelProps {
  projectId: string;
  projectName?: string;
  isOpen: boolean;
  onClose: () => void;
}

export function AIChatPanel({ projectId, projectName, isOpen, onClose }: AIChatPanelProps) {
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen]);

  // Initial greeting if empty
  useEffect(() => {
    if (messages.length === 0) {
      setMessages([
        {
          id: "welcome",
          role: "assistant",
          content: `Hi! I'm your AI task assistant for **${projectName || "this project"}**. I can draft tasks, break down work into subtasks, summarize status, and help plan your workflows.\n\n*Rule: I propose changes for your review; nothing is modified until you confirm.*`,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    }
  }, [projectName]);

  // Chat Mutation
  const chatMutation = useMutation({
    mutationFn: (userMessage: string) =>
      apiFetch<any>(`/projects/${projectId}/ai/chat`, {
        method: "POST",
        body: JSON.stringify({
          message: userMessage,
          conversation_id: conversationId || undefined,
        }),
      }),
    onSuccess: (data) => {
      if (data.conversation_id) {
        setConversationId(data.conversation_id);
      }
      setMessages((prev) => [
        ...prev,
        {
          id: String(Date.now()),
          role: "assistant",
          content: data.message,
          proposal: data.proposal,
          read_results: data.read_results,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    },
    onError: (err: any) => {
      setMessages((prev) => [
        ...prev,
        {
          id: String(Date.now()),
          role: "assistant",
          content: `⚠️ Error: ${err.message || "Unable to reach AI assistant. Please try again."}`,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    },
  });

  // Confirm Proposal Mutation
  const confirmMutation = useMutation({
    mutationFn: (proposalId: string) =>
      apiFetch<Proposal>(`/ai/proposals/${proposalId}/confirm`, {
        method: "POST",
      }),
    onSuccess: (updatedProposal) => {
      // Refresh task list
      queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
      // Update local proposal state
      setMessages((prev) =>
        prev.map((msg) =>
          msg.proposal?.id === updatedProposal.id
            ? { ...msg, proposal: { ...msg.proposal, status: "confirmed" } }
            : msg
        )
      );
    },
  });

  // Reject Proposal Mutation
  const rejectMutation = useMutation({
    mutationFn: (proposalId: string) =>
      apiFetch<Proposal>(`/ai/proposals/${proposalId}/reject`, {
        method: "POST",
      }),
    onSuccess: (updatedProposal) => {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.proposal?.id === updatedProposal.id
            ? { ...msg, proposal: { ...msg.proposal, status: "rejected" } }
            : msg
        )
      );
    },
  });

  const handleSend = (text?: string) => {
    const toSend = text || input;
    if (!toSend.trim() || chatMutation.isPending) return;

    const userMsg: ChatMessage = {
      id: String(Date.now()),
      role: "user",
      content: toSend.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    chatMutation.mutate(toSend.trim());
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!isOpen) return null;

  return (
    <aside className="fixed inset-y-0 right-0 z-40 flex w-full flex-col border-l border-slate-200 bg-white shadow-2xl transition-all sm:w-96 md:w-[420px]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-900 px-4 py-3.5 text-white">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/20 text-indigo-400">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold tracking-tight text-white">TaskPilot AI</h3>
              <span className="rounded bg-indigo-500/20 px-1.5 py-0.5 text-[10px] font-medium text-indigo-300">
                Phase 2
              </span>
            </div>
            <p className="text-xs text-slate-400">Propose & Confirm Agent</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Safety Notice */}
      <div className="flex items-center gap-2 border-b border-indigo-50 bg-indigo-50/60 px-4 py-2 text-xs text-indigo-900">
        <ShieldCheck className="h-3.5 w-3.5 shrink-0 text-indigo-600" />
        <span>Permission-checked: AI only proposes changes for your approval.</span>
      </div>

      {/* Message List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}
          >
            <div className="flex items-center gap-1.5 text-[11px] text-slate-400 mb-1 px-1">
              {msg.role === "user" ? (
                <>
                  <span>You</span>
                  <UserIcon className="h-3 w-3" />
                </>
              ) : (
                <>
                  <Bot className="h-3 w-3 text-indigo-600" />
                  <span>TaskPilot AI</span>
                </>
              )}
              <span>•</span>
              <span>{msg.timestamp}</span>
            </div>

            <div
              className={`max-w-[88%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-xs ${
                msg.role === "user"
                  ? "bg-indigo-600 text-white rounded-br-xs"
                  : "bg-white text-slate-800 border border-slate-200/80 rounded-bl-xs"
              }`}
            >
              <div className="whitespace-pre-wrap">{msg.content}</div>

              {/* Read Results preview if any */}
              {msg.read_results && msg.read_results.length > 0 && (
                <div className="mt-2.5 rounded-lg border border-slate-200 bg-slate-50 p-2 text-xs">
                  <div className="font-semibold text-slate-700 mb-1">Retrieved Workspace Data:</div>
                  {msg.read_results.map((r, i) => (
                    <div key={i} className="text-slate-600 text-[11px]">
                      {Array.isArray(r.result) ? (
                        <ul className="list-disc pl-4 space-y-0.5">
                          {r.result.map((item: any, idx: number) => (
                            <li key={idx}>
                              <span className="font-medium text-slate-900">{item.code}:</span> {item.title} ({item.status})
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <div>{JSON.stringify(r.result)}</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Interactive Proposal Card */}
            {msg.proposal && (
              <div className="mt-2.5 w-full rounded-xl border border-amber-200 bg-white p-3.5 shadow-sm">
                <div className="flex items-center justify-between pb-2 border-b border-amber-100">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-800">
                    <Clock className="h-3.5 w-3.5" />
                    <span>AI Action Proposal</span>
                  </div>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                      msg.proposal.status === "confirmed"
                        ? "bg-emerald-100 text-emerald-800"
                        : msg.proposal.status === "rejected"
                        ? "bg-rose-100 text-rose-800"
                        : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {msg.proposal.status}
                  </span>
                </div>

                <p className="mt-2 text-xs text-slate-600">{msg.proposal.explanation}</p>

                {/* Actions List */}
                <div className="mt-2.5 space-y-1.5">
                  {msg.proposal.actions.map((act, idx) => (
                    <div
                      key={idx}
                      className="flex items-start gap-2 rounded-lg bg-slate-50 p-2 text-xs border border-slate-100"
                    >
                      <ArrowRight className="h-3.5 w-3.5 shrink-0 text-indigo-500 mt-0.5" />
                      <div className="flex-1">
                        <span className="font-semibold text-slate-800 capitalize">
                          {act.tool.replace(/_/g, " ")}:
                        </span>{" "}
                        <span className="text-slate-700">{act.args.title || act.args.status || JSON.stringify(act.args)}</span>
                        {act.args.priority && (
                          <span className="ml-1.5 rounded bg-slate-200 px-1 py-0.2 text-[10px] uppercase font-mono text-slate-700">
                            {act.args.priority}
                          </span>
                        )}
                        {act.args.subtasks && act.args.subtasks.length > 0 && (
                          <div className="mt-1 pl-2 text-[11px] text-slate-500">
                            Subtasks: {act.args.subtasks.map((s: any) => s.title || s).join(", ")}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Confirm / Reject Buttons */}
                {msg.proposal.status === "pending" && (
                  <div className="mt-3 flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                    <button
                      onClick={() => rejectMutation.mutate(msg.proposal!.id)}
                      disabled={rejectMutation.isPending || confirmMutation.isPending}
                      className="flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-50"
                    >
                      <XCircle className="h-3.5 w-3.5 text-slate-400" />
                      Reject
                    </button>
                    <button
                      onClick={() => confirmMutation.mutate(msg.proposal!.id)}
                      disabled={confirmMutation.isPending || rejectMutation.isPending}
                      className="flex items-center gap-1 rounded-lg bg-emerald-600 px-3 py-1 text-xs font-semibold text-white hover:bg-emerald-700 shadow-xs disabled:opacity-50"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      {confirmMutation.isPending ? "Applying..." : "Confirm & Execute"}
                    </button>
                  </div>
                )}

                {msg.proposal.status === "confirmed" && (
                  <div className="mt-2 flex items-center gap-1.5 text-xs font-medium text-emerald-700">
                    <CheckCircle2 className="h-4 w-4" />
                    <span>Applied to project board</span>
                  </div>
                )}

                {msg.proposal.status === "rejected" && (
                  <div className="mt-2 flex items-center gap-1.5 text-xs font-medium text-rose-600">
                    <XCircle className="h-4 w-4" />
                    <span>Proposal rejected</span>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {chatMutation.isPending && (
          <div className="flex items-start gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded bg-indigo-100 text-indigo-600">
              <Bot className="h-3.5 w-3.5 animate-spin" />
            </div>
            <div className="rounded-2xl bg-white border border-slate-200 px-4 py-2 text-xs text-slate-500 shadow-xs animate-pulse">
              TaskPilot AI is thinking...
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Quick Prompts */}
      <div className="border-t border-slate-200 bg-white px-3 py-2">
        <div className="text-[11px] font-medium text-slate-400 mb-1.5">Suggested Prompts:</div>
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => handleSend("Create task for morning housekeeping room inspection")}
            className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] text-slate-700 hover:border-indigo-300 hover:bg-indigo-50 transition-colors"
          >
            + Create inspection task
          </button>
          <button
            onClick={() => handleSend("List all tasks in this project")}
            className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] text-slate-700 hover:border-indigo-300 hover:bg-indigo-50 transition-colors"
          >
            📋 List tasks
          </button>
          <button
            onClick={() => handleSend("Summarize project progress and risks")}
            className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] text-slate-700 hover:border-indigo-300 hover:bg-indigo-50 transition-colors"
          >
            📊 Summarize project
          </button>
        </div>
      </div>

      {/* Input Form */}
      <div className="border-t border-slate-200 bg-white p-3">
        <div className="flex items-end gap-2 rounded-xl border border-slate-300 bg-white p-2 shadow-xs focus-within:border-indigo-600 focus-within:ring-1 focus-within:ring-indigo-600">
          <textarea
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask AI to create tasks, update status, or summarize..."
            className="w-full resize-none border-none p-1 text-xs outline-none text-slate-800 placeholder:text-slate-400"
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || chatMutation.isPending}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:bg-slate-200 disabled:text-slate-400 transition-colors"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
        <div className="mt-1 flex items-center justify-between px-1 text-[10px] text-slate-400">
          <span>Press Enter to send, Shift+Enter for newline</span>
          <span>Tokens metered</span>
        </div>
      </div>
    </aside>
  );
}
