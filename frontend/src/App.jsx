import { useState, useEffect, useRef } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [convoId, setConvoId] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [addedTasks, setAddedTasks] = useState(new Set());
  const messagesEndRef = useRef(null);

  const loadTasks = async () => {
    try {
      const res = await fetch(`${API}/tasks`);
      if (res.ok) {
        const data = await res.json();
        setTasks(data);
      }
    } catch (err) {
      console.error("Failed to load tasks:", err);
    }
  };

  useEffect(() => {
    loadTasks();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = async (overrideText) => {
    const textToSend = typeof overrideText === "string" ? overrideText : input;
    if (!textToSend.trim() || loading) return;

    const userMsg = { role: "user", content: textToSend };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: textToSend, conversation_id: convoId }),
      });
      const data = await res.json();
      setConvoId(data.conversation_id);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: data.reply,
          suggested: data.suggested_tasks || [],
        },
      ]);
    } catch (err) {
      console.error("Chat error:", err);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: "Sorry, I could not reach the server. Make sure the backend is running at " + API,
          suggested: [],
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const addTask = async (t, key) => {
    try {
      const res = await fetch(`${API}/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: t.title,
          description: t.description || "",
          priority: t.priority || "medium",
          subtasks: t.subtasks || [],
        }),
      });
      if (res.ok) {
        if (key !== undefined) {
          setAddedTasks((prev) => new Set(prev).add(key));
        }
        await loadTasks();
      }
    } catch (err) {
      console.error("Failed to add task:", err);
    }
  };

  const toggle = async (t) => {
    const subtasks = t.subtasks || [];
    const hasIncompleteSubtasks = subtasks.some((st) => st.status !== "done");

    // Prevent directly completing parent task if subtasks are incomplete
    if (t.status === "todo" && hasIncompleteSubtasks) {
      setErrorMsg(`⚠️ Cannot mark "${t.title}" complete directly! Please finish all subtasks first.`);
      setTimeout(() => setErrorMsg(""), 3500);
      return;
    }

    try {
      const res = await fetch(`${API}/tasks/${t.id}/toggle`, { method: "PATCH" });
      if (!res.ok) {
        const data = await res.json();
        setErrorMsg(data.detail || "Cannot toggle task");
        setTimeout(() => setErrorMsg(""), 3500);
      }
      await loadTasks();
    } catch (err) {
      console.error("Failed to toggle task:", err);
    }
  };

  const toggleSubtask = async (e, subtaskId) => {
    e.stopPropagation();
    try {
      await fetch(`${API}/subtasks/${subtaskId}/toggle`, { method: "PATCH" });
      await loadTasks();
    } catch (err) {
      console.error("Failed to toggle subtask:", err);
    }
  };

  const isTaskAlreadyPresent = (taskTitle) => {
    if (!taskTitle) return false;
    const clean = taskTitle.toLowerCase().trim();
    return tasks.some((existing) => existing.title.toLowerCase().trim() === clean);
  };

  const getPriorityBadgeStyle = (priority) => {
    switch (priority) {
      case "high":
        return { background: "#fee2e2", color: "#b91c1c", border: "1px solid #fca5a5" };
      case "medium":
        return { background: "#fef3c7", color: "#b45309", border: "1px solid #fcd34d" };
      case "low":
        return { background: "#ecfdf5", color: "#047857", border: "1px solid #a7f3d0" };
      default:
        return { background: "#f1f5f9", color: "#475569", border: "1px solid #cbd5e1" };
    }
  };

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: "24px 20px" }}>
      {/* Toast Alert for Validation */}
      {errorMsg && (
        <div
          style={{
            position: "fixed",
            top: 20,
            right: 20,
            background: "#fee2e2",
            border: "1px solid #ef4444",
            color: "#991b1b",
            padding: "12px 18px",
            borderRadius: 8,
            boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
            zIndex: 9999,
            fontWeight: 500,
            fontSize: "0.9rem",
          }}
        >
          {errorMsg}
        </div>
      )}

      {/* Header */}
      <header style={{ marginBottom: 24, paddingBottom: 16, borderBottom: "1px solid #e2e8f0" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <h1 style={{ fontSize: "1.75rem", fontWeight: 700, color: "#0f172a" }}>
              ✈️ TaskPilot
            </h1>
            <p style={{ color: "#64748b", fontSize: "0.95rem", marginTop: 4 }}>
              AI-powered task assistant with subtasks, function calling, and SQLite persistence
            </p>
          </div>
          {convoId && (
            <span style={{ fontSize: "0.85rem", background: "#f1f5f9", padding: "4px 10px", borderRadius: 9999, color: "#475569" }}>
              Conversation #{convoId}
            </span>
          )}
        </div>
      </header>

      {/* Main Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: 24 }}>
        {/* Chat Section */}
        <section
          style={{
            background: "#ffffff",
            borderRadius: 12,
            border: "1px solid #e2e8f0",
            display: "flex",
            flexDirection: "column",
            height: "75vh",
            boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
          }}
        >
          <div style={{ padding: "16px 20px", borderBottom: "1px solid #f1f5f9", fontWeight: 600, color: "#1e293b" }}>
            💬 Chat with TaskPilot
          </div>

          {/* Messages list */}
          <div style={{ flex: 1, overflowY: "auto", padding: 20, display: "flex", flexDirection: "column", gap: 16 }}>
            {messages.length === 0 && (
              <div style={{ margin: "auto", textAlign: "center", color: "#94a3b8", maxWidth: 400 }}>
                <p style={{ fontSize: "1.1rem", fontWeight: 500, color: "#475569", marginBottom: 8 }}>
                  Start planning your work!
                </p>
                <p style={{ fontSize: "0.9rem", marginBottom: 16 }}>
                  Try asking to plan a project or large goal (it breaks big tasks into subtasks):
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <button
                    onClick={() => send("I need to launch my website: finish landing page, set up analytics, and configure custom domain")}
                    style={{
                      background: "#f8fafc",
                      border: "1px solid #e2e8f0",
                      padding: "8px 12px",
                      borderRadius: 8,
                      fontSize: "0.85rem",
                      color: "#334155",
                      textAlign: "left",
                    }}
                  >
                    🚀 "I need to launch my website: finish landing page, set up analytics, and configure custom domain"
                  </button>
                  <button
                    onClick={() => send("Hi there, how does TaskPilot work?")}
                    style={{
                      background: "#f8fafc",
                      border: "1px solid #e2e8f0",
                      padding: "8px 12px",
                      borderRadius: 8,
                      fontSize: "0.85rem",
                      color: "#334155",
                      textAlign: "left",
                    }}
                  >
                    👋 "Hi there, how does TaskPilot work?"
                  </button>
                </div>
              </div>
            )}

            {messages.map((m, i) => (
              <div
                key={i}
                style={{
                  alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                  maxWidth: "85%",
                }}
              >
                <div
                  style={{
                    background: m.role === "user" ? "#2563eb" : "#f8fafc",
                    color: m.role === "user" ? "#ffffff" : "#1e293b",
                    padding: "12px 16px",
                    borderRadius: 12,
                    border: m.role === "user" ? "none" : "1px solid #e2e8f0",
                    fontSize: "0.95rem",
                  }}
                >
                  <div style={{ fontSize: "0.75rem", opacity: 0.8, marginBottom: 4, textTransform: "capitalize" }}>
                    {m.role}
                  </div>
                  <div style={{ whiteSpace: "pre-wrap" }}>{m.content}</div>

                  {/* Suggested tasks list (exclude any task already present in the task list) */}
                  {(() => {
                    const activeSuggestions = (m.suggested || []).filter(
                      (t) => !isTaskAlreadyPresent(t.title)
                    );
                    if (activeSuggestions.length === 0) return null;

                    return (
                      <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid #e2e8f0", display: "flex", flexDirection: "column", gap: 8 }}>
                        <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "#475569" }}>
                          Suggested Tasks:
                        </div>
                        {activeSuggestions.map((t, j) => {
                          const taskKey = `${i}-${j}`;
                          const isAdded = addedTasks.has(taskKey) || isTaskAlreadyPresent(t.title);
                          const subtasks = t.subtasks || [];
                          return (
                            <div
                              key={j}
                              style={{
                                background: "#ffffff",
                                border: "1px solid #cbd5e1",
                                borderRadius: 8,
                                padding: "10px 12px",
                                display: "flex",
                                flexDirection: "column",
                                gap: 6,
                              }}
                            >
                              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                                <div style={{ flex: 1 }}>
                                  <div style={{ fontWeight: 600, fontSize: "0.9rem", color: "#1e293b" }}>
                                    {t.title}
                                  </div>
                                  {t.description && (
                                    <div style={{ fontSize: "0.8rem", color: "#64748b" }}>
                                      {t.description}
                                    </div>
                                  )}
                                  <span
                                    style={{
                                      display: "inline-block",
                                      marginTop: 4,
                                      fontSize: "0.7rem",
                                      fontWeight: 600,
                                      padding: "2px 6px",
                                      borderRadius: 4,
                                      textTransform: "uppercase",
                                      ...getPriorityBadgeStyle(t.priority),
                                    }}
                                  >
                                    {t.priority || "medium"}
                                  </span>
                                </div>
                                <button
                                  disabled={isAdded}
                                  onClick={() => addTask(t, taskKey)}
                                  style={{
                                    background: isAdded ? "#94a3b8" : "#10b981",
                                    color: "#ffffff",
                                    border: "none",
                                    borderRadius: 6,
                                    padding: "6px 12px",
                                    fontSize: "0.8rem",
                                    fontWeight: 600,
                                    alignSelf: "flex-start",
                                  }}
                                >
                                  {isAdded ? "Added ✓" : "Add +"}
                                </button>
                              </div>

                              {/* Show subtasks breakdown in suggestion if present */}
                              {subtasks.length > 0 && (
                                <div
                                  style={{
                                    marginTop: 4,
                                    paddingLeft: 10,
                                    borderLeft: "2px solid #e2e8f0",
                                    display: "flex",
                                    flexDirection: "column",
                                    gap: 2,
                                  }}
                                >
                                  <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "#64748b" }}>
                                    Includes {subtasks.length} Subtasks:
                                  </div>
                                  {subtasks.map((st, k) => (
                                    <div key={k} style={{ fontSize: "0.78rem", color: "#475569" }}>
                                      • {typeof st === "string" ? st : st.title}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    );
                  })()}
                </div>
              </div>
            ))}

            {loading && (
              <div style={{ alignSelf: "flex-start", background: "#f1f5f9", padding: "10px 16px", borderRadius: 12, color: "#64748b", fontSize: "0.9rem" }}>
                Thinking...
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Bar */}
          <div style={{ padding: "14px 16px", borderTop: "1px solid #f1f5f9", display: "flex", gap: 10 }}>
            <input
              style={{
                flex: 1,
                padding: "10px 14px",
                border: "1px solid #cbd5e1",
                borderRadius: 8,
                fontSize: "0.95rem",
                outline: "none",
              }}
              placeholder="e.g. Plan my product launch or organize home tasks..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
              disabled={loading}
            />
            <button
              onClick={() => send()}
              disabled={loading || !input.trim()}
              style={{
                background: loading || !input.trim() ? "#94a3b8" : "#2563eb",
                color: "#ffffff",
                border: "none",
                borderRadius: 8,
                padding: "0 20px",
                fontWeight: 600,
                fontSize: "0.95rem",
              }}
            >
              Send
            </button>
          </div>
        </section>

        {/* Tasks Section */}
        <section
          style={{
            background: "#ffffff",
            borderRadius: 12,
            border: "1px solid #e2e8f0",
            display: "flex",
            flexDirection: "column",
            height: "75vh",
            boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
          }}
        >
          <div
            style={{
              padding: "16px 20px",
              borderBottom: "1px solid #f1f5f9",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div style={{ fontWeight: 600, color: "#1e293b" }}>
              📋 Tasks ({tasks.filter((t) => t.status === "done").length}/{tasks.length})
            </div>
            <button
              onClick={loadTasks}
              style={{
                background: "transparent",
                border: "1px solid #e2e8f0",
                borderRadius: 6,
                padding: "4px 8px",
                fontSize: "0.8rem",
                color: "#64748b",
              }}
            >
              ↻ Refresh
            </button>
          </div>

          <div style={{ flex: 1, overflowY: "auto", padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
            {tasks.length === 0 ? (
              <div style={{ margin: "auto", textAlign: "center", color: "#94a3b8" }}>
                No tasks yet. Ask TaskPilot to suggest some or add them from the chat!
              </div>
            ) : (
              tasks.map((t) => {
                const subtasks = t.subtasks || [];
                const hasSubtasks = subtasks.length > 0;
                const completedCount = subtasks.filter((st) => st.status === "done").length;
                const hasIncomplete = subtasks.some((st) => st.status !== "done");

                return (
                  <div
                    key={t.id}
                    style={{
                      borderRadius: 8,
                      border: "1px solid #e2e8f0",
                      background: t.status === "done" ? "#f8fafc" : "#ffffff",
                      padding: "12px 14px",
                      display: "flex",
                      flexDirection: "column",
                      gap: 8,
                      boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
                    }}
                  >
                    <div
                      onClick={() => toggle(t)}
                      style={{
                        display: "flex",
                        alignItems: "flex-start",
                        gap: 12,
                        cursor: hasSubtasks && hasIncomplete && t.status === "todo" ? "not-allowed" : "pointer",
                      }}
                      title={hasSubtasks && hasIncomplete && t.status === "todo" ? "Finish all subtasks first to complete this task" : "Click to toggle task"}
                    >
                      <span style={{ fontSize: "1.2rem", lineHeight: 1 }}>
                        {t.status === "done" ? "✅" : hasSubtasks && hasIncomplete ? "🔒" : "⬜"}
                      </span>
                      <div style={{ flex: 1 }}>
                        <div
                          style={{
                            fontWeight: 600,
                            fontSize: "0.95rem",
                            color: t.status === "done" ? "#94a3b8" : "#1e293b",
                            textDecoration: t.status === "done" ? "line-through" : "none",
                          }}
                        >
                          {t.title}
                        </div>
                        {t.description && (
                          <div
                            style={{
                              fontSize: "0.8rem",
                              color: t.status === "done" ? "#cbd5e1" : "#64748b",
                              marginTop: 2,
                            }}
                          >
                            {t.description}
                          </div>
                        )}
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
                          <span
                            style={{
                              display: "inline-block",
                              fontSize: "0.7rem",
                              fontWeight: 600,
                              padding: "2px 6px",
                              borderRadius: 4,
                              textTransform: "uppercase",
                              ...getPriorityBadgeStyle(t.priority),
                            }}
                          >
                            {t.priority || "medium"}
                          </span>

                          {hasSubtasks && (
                            <span
                              style={{
                                fontSize: "0.75rem",
                                color: t.status === "done" ? "#047857" : "#64748b",
                                background: t.status === "done" ? "#ecfdf5" : "#f1f5f9",
                                padding: "2px 8px",
                                borderRadius: 4,
                                fontWeight: 500,
                              }}
                            >
                              Subtasks: {completedCount}/{subtasks.length} {t.status === "done" && "✓ Done"}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Subtasks rendering */}
                    {hasSubtasks && (
                      <div
                        style={{
                          marginTop: 4,
                          paddingLeft: 30,
                          borderTop: "1px dashed #e2e8f0",
                          paddingTop: 8,
                          display: "flex",
                          flexDirection: "column",
                          gap: 6,
                        }}
                      >
                        {subtasks.map((st) => (
                          <div
                            key={st.id}
                            onClick={(e) => toggleSubtask(e, st.id)}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: 8,
                              fontSize: "0.85rem",
                              cursor: "pointer",
                              color: st.status === "done" ? "#94a3b8" : "#334155",
                              textDecoration: st.status === "done" ? "line-through" : "none",
                            }}
                          >
                            <span style={{ fontSize: "1rem", lineHeight: 1 }}>
                              {st.status === "done" ? "✅" : "⬜"}
                            </span>
                            <span>{st.title}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
