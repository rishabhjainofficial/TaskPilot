"""
Tool definitions and execution dispatch for AI Agent.
Distinguishes between read-only tools (auto-executed) and write actions (require PROPOSE/CONFIRM).
"""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a new task in the current project",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Actionable verb-first task title"},
                    "description": {"type": "string", "description": "Details or SOP instructions"},
                    "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                    "due_date": {"type": "string", "description": "ISO date format (YYYY-MM-DD)"},
                    "estimated_hours": {"type": "integer"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_subtask",
            "description": "Create a subtask under an existing parent task",
            "parameters": {
                "type": "object",
                "properties": {
                    "parent_task_title_or_code": {"type": "string", "description": "Parent task title or code (e.g. FLT-1)"},
                    "title": {"type": "string", "description": "Actionable subtask title"},
                    "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                },
                "required": ["parent_task_title_or_code", "title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task_status",
            "description": "Change the status of a task or subtask",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_title_or_code": {"type": "string", "description": "Title or task code (e.g. OPS-12)"},
                    "status": {"type": "string", "enum": ["backlog", "todo", "in_progress", "in_review", "done", "blocked"]},
                },
                "required": ["task_title_or_code", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assign_task",
            "description": "Assign a task to a team member by email or name",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_title_or_code": {"type": "string"},
                    "assignee_email_or_name": {"type": "string"},
                },
                "required": ["task_title_or_code", "assignee_email_or_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "suggest_tasks",
            "description": "Generate a batch of actionable tasks with optional subtasks",
            "parameters": {
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                                "subtasks": {
                                    "type": "array",
                                    "items": {"type": "object", "properties": {"title": {"type": "string"}}},
                                },
                            },
                            "required": ["title"],
                        },
                    }
                },
                "required": ["tasks"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "List all tasks and subtasks in the project",
            "parameters": {
                "type": "object",
                "properties": {
                    "status_filter": {"type": "string", "description": "Optional status filter (e.g. 'todo', 'done')"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_workspace",
            "description": "Search for keywords across project tasks and descriptions",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keyword or phrase"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_project",
            "description": "Summarize project progress, completion rates, and open blockers",
            "parameters": {
                "type": "object",
                "properties": {
                    "focus": {"type": "string", "enum": ["overview", "blockers", "standup"]},
                },
            },
        },
    },
]

# Write tools that MUST be proposed and confirmed by human before touching DB
WRITE_TOOLS = {
    "create_task",
    "create_subtask",
    "update_task_status",
    "assign_task",
    "suggest_tasks",
}
