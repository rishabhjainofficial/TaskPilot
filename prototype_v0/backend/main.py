from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from database import SessionLocal, Conversation, Message, Task, SubTask, init_db
from agent import run_agent

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database tables exist on startup
    try:
        init_db()
    except Exception as e:
        print(f"Database initialization error (will retry on requests): {e}")
    yield

app = FastAPI(title="TaskPilot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def serialize_task(t: Task) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "priority": t.priority,
        "status": t.status,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "subtasks": [
            {
                "id": st.id,
                "task_id": st.task_id,
                "title": st.title,
                "status": st.status,
                "created_at": st.created_at.isoformat() if st.created_at else None,
            }
            for st in (t.subtasks or [])
        ],
    }

class ChatIn(BaseModel):
    message: str
    conversation_id: int | None = None

class SubTaskIn(BaseModel):
    title: str

class TaskIn(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"
    subtasks: list[Any] = []

@app.get("/")
def root():
    return {"status": "ok", "message": "TaskPilot API is running"}

@app.post("/chat")
def chat(body: ChatIn):
    db = SessionLocal()
    try:
        convo = db.get(Conversation, body.conversation_id) if body.conversation_id else None
        if not convo:
            convo = Conversation()
            db.add(convo)
            db.commit()
            db.refresh(convo)

        db.add(Message(conversation_id=convo.id, role="user", content=body.message))
        db.commit()

        rows = db.query(Message).filter_by(conversation_id=convo.id).order_by(Message.id).all()
        history = [{"role": m.role, "content": m.content} for m in rows]

        # Retrieve all existing task titles from the database
        existing_tasks = [t.title for t in db.query(Task).all()]

        result = run_agent(history, existing_tasks=existing_tasks)
        db.add(Message(conversation_id=convo.id, role="assistant", content=result["reply"]))
        db.commit()
        return {"conversation_id": convo.id, **result}
    finally:
        db.close()

@app.get("/tasks")
def list_tasks():
    db = SessionLocal()
    try:
        tasks = db.query(Task).order_by(Task.id.desc()).all()
        return [serialize_task(t) for t in tasks]
    finally:
        db.close()

@app.post("/tasks")
def create_task(t: TaskIn):
    db = SessionLocal()
    try:
        task = Task(
            title=t.title.strip(),
            description=t.description or "",
            priority=t.priority or "medium",
            status="todo",
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        # Attach subtasks if provided
        for item in t.subtasks:
            if isinstance(item, dict):
                sub_title = str(item.get("title", ""))
            elif isinstance(item, str):
                sub_title = item
            elif hasattr(item, "title") and not callable(getattr(item, "title")):
                sub_title = str(getattr(item, "title", ""))
            else:
                sub_title = str(item)
            
            sub_title = sub_title.strip()
            if sub_title:
                subtask = SubTask(task_id=task.id, title=sub_title, status="todo")
                db.add(subtask)

        db.commit()
        db.refresh(task)
        return serialize_task(task)
    finally:
        db.close()

@app.post("/tasks/{task_id}/subtasks")
def add_subtask(task_id: int, st: SubTaskIn):
    db = SessionLocal()
    try:
        task = db.get(Task, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        title = st.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="Subtask title cannot be empty")

        subtask = SubTask(task_id=task.id, title=title, status="todo")
        db.add(subtask)
        # Adding an unfinished subtask resets task status to todo if it was completed
        task.status = "todo"
        db.commit()
        db.refresh(task)
        return serialize_task(task)
    finally:
        db.close()

@app.patch("/tasks/{task_id}/toggle")
def toggle_task(task_id: int):
    db = SessionLocal()
    try:
        task = db.get(Task, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        # If task has subtasks:
        if task.subtasks:
            if task.status == "todo":
                # Check if all subtasks are done
                has_incomplete_subtasks = any(st.status != "done" for st in task.subtasks)
                if has_incomplete_subtasks:
                    raise HTTPException(
                        status_code=400,
                        detail="Cannot mark task as complete directly when it has incomplete subtasks. Complete all subtasks first."
                    )
                task.status = "done"
            else:
                # Toggling from done to todo
                task.status = "todo"
        else:
            # No subtasks: direct toggle allowed
            task.status = "done" if task.status == "todo" else "todo"

        db.commit()
        db.refresh(task)
        return serialize_task(task)
    finally:
        db.close()

@app.patch("/subtasks/{subtask_id}/toggle")
def toggle_subtask(subtask_id: int):
    db = SessionLocal()
    try:
        subtask = db.get(SubTask, subtask_id)
        if not subtask:
            raise HTTPException(status_code=404, detail="Subtask not found")

        subtask.status = "done" if subtask.status == "todo" else "todo"
        db.commit()

        # Update parent task status automatically:
        # If ALL subtasks are done -> task is marked done
        # If ANY subtask is todo -> task is marked todo
        task = db.get(Task, subtask.task_id)
        if task and task.subtasks:
            all_done = all(st.status == "done" for st in task.subtasks)
            task.status = "done" if all_done else "todo"
            db.commit()
            db.refresh(task)
            return serialize_task(task)

        return {"id": subtask.id, "status": subtask.status}
    finally:
        db.close()
