# ✈️ TaskPilot SaaS

A multi-tenant, AI-powered team task management platform.
Built with **FastAPI**, **PostgreSQL 16 + pgvector** (with native Row-Level Security for multi-tenancy), **SQLAlchemy 2.0 (async)**, **Alembic**, **Redis**, **ARQ**, and **Next.js (App Router)** with **TypeScript** and **Tailwind CSS**.

---

## 🏗️ Architecture Overview

```
[ Client: Next.js (App Router) ] (http://localhost:3000)
                │
                │ HTTP REST (JSON) + Bearer JWT
                ▼
[ Backend: FastAPI (Async) ] (http://localhost:8000)
  ├── Auth: Argon2id + PyJWT (email verification, invite links, refresh rotation)
  ├── RBAC: Central has_permission() engine backed by DB-seeded permission sets
  ├── Tenant Context: SET LOCAL app.current_org inside explicit transaction
  └── Task Numbering: Auto-incrementing project-scoped task codes (e.g. OPS-1)
                │
                ├─────────────────────────────┬─────────────────────────────┐
                ▼                             ▼                             ▼
[ PostgreSQL 16 + pgvector ]          [ Redis 7 + ARQ ]            [ MinIO Storage ]
- Row-Level Security on all tenant    - Background workers         - S3-compatible file
  tables (USING & WITH CHECK)         - Token rate limiting          storage
- Isolated tenant data access
```

---

## 🚀 Quickstart Guide

### 1. Run Everything with Docker Compose

Ensure Docker is installed and running on your system, then start all services:

```bash
docker compose up --build
```

Services started:
- **Frontend**: `http://localhost:3000` (Next.js App Router UI)
- **Backend API**: `http://localhost:8000` (FastAPI)
- **Swagger API Docs**: `http://localhost:8000/docs`
- **PostgreSQL 16**: `localhost:5432` (`taskpilot` / `taskpilot_dev`)
- **Redis 7**: `localhost:6379`
- **MinIO Console**: `http://localhost:9001` (`minioadmin` / `minioadmin`)

---

### 2. Run Locally in Development Mode (Without Docker)

#### A. Backend Setup
1. Open a terminal and enter the `backend/` directory:
   ```bash
   cd backend
   ```
2. Activate your virtual environment:
   ```bash
   source .venv/bin/activate
   ```
3. Run database migrations:
   ```bash
   alembic upgrade head
   ```
4. Seed default permissions and role bundles:
   ```bash
   python -m seeds.seed_roles_permissions
   ```
5. Start the backend development server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

#### B. Frontend Setup
1. In a new terminal, enter the `frontend/` directory:
   ```bash
   cd frontend
   ```
2. Start the Next.js development server:
   ```bash
   npm run dev
   ```
3. Open `http://localhost:3000` in your browser.

---

## 🧪 Running Automated Tests

Run the backend test suite:
```bash
cd backend
.venv/bin/pytest -v
```

The test suite covers:
- **Tenant Isolation**: Proving Org A cannot read, query, forge headers, or modify Org B's projects and tasks.
- **Permission Matrix**: Verifying Owner, Admin, Manager, and Member role boundaries across operations.
- **Authentication**: Argon2id password hashing, email verification token verification, JWT issuance, refresh token rotation, and invite acceptance.
- **Task & Subtask Guardrails**: Auto-incrementing task numbering (e.g. `FLT-1`), subtask hierarchy, preventing premature completion when subtasks remain, and automatic parent task completion when all subtasks are finished.

---

## 📋 Phase 1 Scope & Status

- [x] Multi-service `docker-compose.yml` (PostgreSQL + pgvector, Redis, MinIO, Backend, Worker, Frontend)
- [x] PostgreSQL Row-Level Security (RLS) policies with both `USING` and `WITH CHECK`
- [x] Central RBAC engine (`has_permission`) with DB-seeded permissions
- [x] Argon2id password hashing + PyJWT access & refresh tokens
- [x] Organization & Project management with per-project task sequence numbering (`KEY-NUMBER`)
- [x] Tasks & subtasks with hierarchy, guardrails, and auto-completion
- [x] Audit logging infrastructure (platform & tenant events)
- [x] Automated tenant isolation, permission matrix, and auth test suite (11/11 passing)
- [x] Next.js (App Router) + TypeScript + Tailwind CSS UI (Auth + Dashboard + Project Board)
