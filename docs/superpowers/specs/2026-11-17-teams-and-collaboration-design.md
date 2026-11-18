# Design Document: Teams, Roles & Everyday Task Collaboration (Phase 3)

**Date**: 2026-11-17  
**Status**: Pending Review & Builder Check  
**Author**: Antigravity & User  
**Target Phase**: Phase 3 of TaskPilot SaaS  

---

## 1. Intent & The Why

In Phase 1 and Phase 2, TaskPilot established a rock-solid multi-tenant foundation (PostgreSQL RLS with `USING` and `WITH CHECK`, Argon2id auth, 3-tier RBAC, tasks/subtasks CRUD, auto-numbering) and a permission-enforced AI Chat Agent (Propose then Confirm flow with persistent `ai_proposals`).

However, the product is currently missing the **core daily collaboration loop**:
- **Organizations cannot group employees into teams or designate Team Leads**.
- **Employees have no job title / specialization metadata** (e.g. Backend Dev, Frontend Dev, Tester, UI/UX, Senior Dev).
- **Users cannot discuss work in task comments, attach deliverables or screenshots, or log hours spent**.
- **The AI cannot make intelligent task assignment recommendations** because it lacks visibility into team roles and job specializations.

This design document specifies **Phase 3: Teams, Roles & Everyday Task Collaboration**, completing the daily operational loop so organizations can actually execute work, assign teams, track time, attach files, and communicate within tasks.

---

## 2. Goals, Non-Goals, and Anti-Goals

### Goals
1. **Teams & Team Roles**:
   - Managers and Admins can create teams within their organization.
   - Designate at most one `team_role = 'lead'` per team (enforced by a PostgreSQL unique partial index).
   - Assign member `job_title` free-text or configurable tags (e.g. "Backend Developer", "Tester", "UI/UX Designer") used for display and AI recommendations.
2. **Project-to-Team Assignments**:
   - Assign projects to entire teams or individual users via `project_assignments`.
   - Team Leads gain task management permissions (`task.create`, `task.delete`, `task.assign`) strictly within projects assigned to their team.
   - Team Members / Employees gain access to view tasks, transition workflow statuses, add comments, upload attachments, and log time.
3. **Threaded Comments (`task_comments`)**:
   - Hierarchical/threaded discussions on tasks (`parent_comment_id`).
   - Tenant-scoped with RLS and cascade deletion on task removal.
4. **Task Attachments (`attachments`)**:
   - Secure S3-compatible file storage (MinIO locally, Cloudflare R2 / AWS S3 in production).
   - Presigned upload URL flow for scalable, direct-to-storage client uploads without backend memory bottlenecks.
   - Complete metadata tracking (`filename`, `storage_key`, `content_type`, `size_bytes`).
5. **Time Tracking (`time_logs`)**:
   - Explicit time logging against tasks (`duration_minutes`, `log_date`, `description`).
   - Summary rollups per task and project.
6. **Role-Aware AI Task Assignment**:
   - Upgrade the AI `assign_task` tool to analyze task requirements and recommend candidates by matching keywords against team members' `job_title` and team memberships.

### Non-Goals
- **Real-Time WebSockets**: Live presence or live cursor updates remain scheduled for Phase 7 (polling/TanStack Query invalidation suffices for Phase 3).
- **Billing Tier Limits on Teams**: Seat and team quantity limits will be wired into Stripe/Razorpay webhooks in Phase 6.
- **Document-to-Plan AI Generation**: Pushed to Phase 4 so it builds on top of real teams and job titles.

### Anti-Goals
- **Dual Source of Truth for Team Leads**: Never maintain a `teams.lead_id` column alongside `team_members.team_role = 'lead'`. The single source of truth is `team_members`.
- **Backend File Proxy Bottleneck**: Do not stream file byte uploads through FastAPI memory or disk for attachments; presigned S3 URLs must be used.
- **Cross-Tenant Storage Leaks**: Storage keys must strictly follow the format `{org_id}/{project_id}/{task_id}/{uuid}-{filename}`, verified against the authenticated tenant context.

---

## 3. Approaches Considered

### Approach 1: Human Collaboration & Daily Work First (Selected)
- **Concept**: Pull Teams, Job Titles, Project-to-Team scoping, Comments, Attachments, and Time Logs into Phase 3. Pushes Document-to-Plan to Phase 4.
- **Pros**:
  - Immediate operational usability: employees and managers can use TaskPilot as a real day-to-day task manager.
  - Provides real team roles and job titles for AI task assignment and future plan generation.
  - Keeps PRs and phases focused and testable.
- **Cons**: AI PDF/DOCX plan generation is deferred to Phase 4.
- **Selection Reason**: Chosen by user because task management without comments, time logs, and attachments is unusable for real teams.

### Approach 2: Monolithic Phase 3 (Doc-to-Plan + Teams + Comments + Time Logs)
- **Concept**: Combine Document-to-Plan, ARQ workers, Teams, Comments, Time Logs, and MinIO uploads all into Phase 3.
- **Trade-off**: High risk of scope creep, bloated implementation, and fragile testing surface. Dropped.

### Approach 3: Stick to Original Sequence (Doc-to-Plan Next, Collaboration Later)
- **Concept**: Build Doc-to-Plan in Phase 3, Teams in Phase 4, and Time Logs / Attachments in Phase 7.
- **Trade-off**: Leaves users unable to log time or attach files for months while building advanced document chunking. Dropped.

---

## 4. Detailed Architecture & Data Model

### 4.1 Database Tables (PostgreSQL 16 + RLS)

All tenant-owned tables enforce RLS:
```sql
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {table}
  USING (org_id = current_setting('app.current_org')::uuid)
  WITH CHECK (org_id = current_setting('app.current_org')::uuid);
```

#### 1. `teams`
```sql
CREATE TABLE teams (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL REFERENCES organizations(id),
    name        VARCHAR(100) NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(org_id, name)
);
```

#### 2. `team_members`
```sql
CREATE TABLE team_members (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL REFERENCES organizations(id),
    team_id     UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    team_role   VARCHAR(20) NOT NULL DEFAULT 'member' CHECK (team_role IN ('lead', 'member')),
    job_title   VARCHAR(100), -- e.g. "Senior Backend Developer", "QA Tester", "UI/UX"
    joined_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(team_id, user_id)
);

-- Crucial: Enforce at most ONE lead per team
CREATE UNIQUE INDEX idx_team_one_lead ON team_members(team_id) WHERE team_role = 'lead';
```

#### 3. `project_assignments` (already partially defined; now fully operational)
```sql
-- Exactly one of user_id or team_id is set
ALTER TABLE project_assignments ADD CONSTRAINT assignment_target CHECK (
    (user_id IS NOT NULL AND team_id IS NULL) OR
    (user_id IS NULL AND team_id IS NOT NULL)
);
CREATE UNIQUE INDEX idx_pa_user ON project_assignments(project_id, user_id) WHERE user_id IS NOT NULL;
CREATE UNIQUE INDEX idx_pa_team ON project_assignments(project_id, team_id) WHERE team_id IS NOT NULL;
```

#### 4. `task_comments`
```sql
CREATE TABLE task_comments (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id            UUID NOT NULL REFERENCES organizations(id),
    task_id           UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id           UUID NOT NULL REFERENCES users(id),
    content           TEXT NOT NULL,
    parent_comment_id UUID REFERENCES task_comments(id) ON DELETE CASCADE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_task_comments_task ON task_comments(task_id, created_at ASC);
```

#### 5. `attachments`
```sql
CREATE TABLE attachments (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id       UUID NOT NULL REFERENCES organizations(id),
    task_id      UUID REFERENCES tasks(id) ON DELETE CASCADE,
    comment_id   UUID REFERENCES task_comments(id) ON DELETE SET NULL,
    user_id      UUID NOT NULL REFERENCES users(id),
    filename     VARCHAR(255) NOT NULL,
    storage_key  TEXT NOT NULL UNIQUE,
    content_type VARCHAR(100) NOT NULL,
    size_bytes   BIGINT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_attachments_task ON attachments(task_id);
```

#### 6. `time_logs`
```sql
CREATE TABLE time_logs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id           UUID NOT NULL REFERENCES organizations(id),
    task_id          UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id          UUID NOT NULL REFERENCES users(id),
    duration_minutes INT NOT NULL CHECK (duration_minutes > 0),
    description      TEXT,
    log_date         DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_time_logs_task ON time_logs(task_id, log_date DESC);
CREATE INDEX idx_time_logs_user ON time_logs(user_id, log_date DESC);
```

---

## 5. Permission Enforcement & Business Rules

### 5.1 Central RBAC Updates & Task Visibility Model (Strict Silo)
The central `has_permission(user, org_id, permission, db, project_id=..., task_id=...)` engine and query filters enforce:

1. **Org Roles**:
   - `owner`: full org access.
   - `admin`: manage teams, members, and all projects.
   - `manager`: can create teams and manage projects assigned to them or their teams.
   - `member`: standard employee access with strict assignment boundaries.

2. **Team Roles & Project Scoping (Strict Silo Model)**:
   - When a project is assigned to a Team (`project_assignments.team_id`), any user who is a member of that team with `team_role = 'lead'` receives team-level management permissions for that project:
     - `task.create`, `task.delete`, `task.assign`, `task.update_any`, `task.view_all`.
     - Team Leads see and manage **all tasks** within their team's assigned projects.
   - Regular `team_role = 'member'` / `org_role = 'member'` users operate under **Strict Silo Visibility**:
     - `task.view_assigned`, `task.update_assigned_status`, `task.comment_assigned`, `task.attach_assigned`, `task.time_log_assigned`.
     - **Visibility Constraint**: When querying `GET /api/v1/projects/{projectId}/tasks`, if the user is a regular member (not Owner/Admin/Manager/Team Lead), the query automatically appends `WHERE tasks.assignee_id = current_user.id`. Unassigned tasks and tasks assigned to other colleagues are completely hidden.
     - Direct task operations (comments, attachments, time logs, status changes) on tasks not assigned to the member return `404 NOT_FOUND` or `403 FORBIDDEN`.

3. **Team Lead Lifecycle & Promotion**:
   - Promoting a new member to `team_role = 'lead'` atomically demotes any existing lead on that team in the same database transaction:
     ```python
     await db.execute(update(TeamMember).where(TeamMember.team_id == team_id, TeamMember.team_role == 'lead').values(team_role='member'))
     await db.execute(update(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == target_user_id).values(team_role='lead'))
     ```
   - This prevents any transient violation of `idx_team_one_lead`.

4. **Deactivation & Reassignment Rules**:
   - When an organization member is deactivated (`memberships.status = 'deactivated'`):
     - They are immediately removed from `team_members` (freeing any Team Lead seat).
     - Any active tasks assigned to them are unassigned (`assignee_id = NULL`).
     - Historical records (`task_comments`, `attachments`, `time_logs`) retain their `user_id` foreign key for auditability.

---

## 6. S3 / MinIO Presigned Upload & Download Architecture

Direct browser-to-storage upload and secure on-demand download avoids server proxying:

1. **Upload Ticket Request**:
   `POST /api/v1/projects/{projectId}/tasks/{taskId}/attachments/upload-url`
   - Payload: `{ filename: "specs.pdf", content_type: "application/pdf", size_bytes: 2048576 }`
   - Server checks permission (assigned user or team lead/manager) and size limit ($\le 25\text{MB}$).
   - Generates storage key: `orgs/{org_id}/projects/{project_id}/tasks/{task_id}/{uuid}_{sanitized_filename}`.
   - Returns presigned PUT URL valid for 15 minutes.

2. **Upload Direct to MinIO/S3**:
   - Browser PUTs bytes directly to the storage bucket.

3. **Upload Confirmation**:
   `POST /api/v1/projects/{projectId}/tasks/{taskId}/attachments/confirm`
   - Server performs an S3 `HeadObject` check to verify the object actually exists and matches size/type, then inserts into `attachments`.

4. **Download / Preview (On-Demand Redirect)**:
   `GET /api/v1/projects/{projectId}/tasks/{taskId}/attachments/{attachmentId}/download`
   - Server verifies user permission on the task.
   - Generates a short-lived (5-minute) presigned S3 GET URL and returns HTTP `307 Temporary Redirect`.
   - Leaves frontend TanStack Query cache stable without expired URL poisoning.

---

## 7. Role-Aware AI Agent Integration

Upgrade `app/ai/tools.py`:
- `assign_task(task_code, suggested_assignee_email_or_role)`:
  - If a role or job title is specified (e.g. "assign to our senior backend dev" or "assign to a tester"), the tool queries `team_members` with matching `job_title` within teams assigned to the project.
  - **Disambiguation**: If multiple team members share the matching title, the AI queries the open task count (`status != 'done'`) for each candidate and proposes the least-loaded member.
  - Generates `AIProposal` explanation: *"Suggested Alice (alice@company.com) - Senior Backend Developer (2 active tasks, compared to Bob with 5 active tasks)"*.

   - Payload: `{ filename: "specs.pdf", content_type: "application/pdf", size_bytes: 2048576 }`
   - Server checks size limit ($\le 25\text{MB}$) and generates storage key:
     `orgs/{org_id}/projects/{project_id}/tasks/{task_id}/{uuid}_{sanitized_filename}`
   - Returns presigned PUT URL valid for 15 minutes.
2. Browser performs direct HTTP PUT to MinIO / S3.
3. Browser confirms upload:
   `POST /api/v1/projects/{projectId}/tasks/{taskId}/attachments/confirm`
   - Server performs an S3 `HeadObject` check to verify the object actually exists, matches expected size/type, and creates the DB record in `attachments`.

---

## 7. Role-Aware AI Agent Integration

Upgrade `app/ai/tools.py`:
- `assign_task(task_code, suggested_assignee_email_or_role)`:
  - If a role or job title is specified (e.g. "assign to our senior backend dev" or "assign to a tester"), the tool queries `team_members` with matching `job_title` within teams assigned to the project.
  - Proposes assignment in an `AIProposal` card with reasoning: *"Suggested Alice (alice@company.com) because her job title is Senior Backend Developer in Core API Team"*.

---

## 8. Frontend Implementation

1. **Team Management View** (`/dashboard/teams` or modal):
   - Create team, view member list, designate Team Lead, assign job titles via quick badge or inline edit.
2. **Task Detail Drawer / Modal**:
   - **Comments Tab**: Chronological threaded comments with Markdown formatting and reply buttons.
   - **Attachments Tab**: File list with download links, file size badges, and drag-and-drop file uploader with upload progress.
   - **Time Logs Tab**: Log hours/minutes with work date and notes; shows total accumulated time logged on the task.

---

## 9. Verification & Testing Plan

1. **Automated Integration Tests**:
   - `test_team_creation_and_single_lead`: Verifies that attempting to set two leads on a single team violates `idx_team_one_lead`.
   - `test_team_lead_project_permissions`: Proves a Team Lead can create tasks in their team's project, but cannot in unassigned projects.
   - `test_member_task_collaboration`: Proves an employee can post comments, log time, and confirm attachments, but cannot delete other users' tasks.
   - `test_time_logs_aggregation`: Verifies duration calculations and tenant isolation on time logs.
   - `test_s3_presigned_attachment_flow`: Mocks S3 client and tests upload-url + confirm flow.
   - `test_ai_role_aware_assignment`: Verifies AI suggests assignees based on team `job_title`.
2. **Frontend Production Build**:
   - Run `npm run build` with zero TypeScript or styling warnings.

---

## 10. What's Left to the Builder
- Selection between AWS SDK (`aiobotocore` / `boto3`) or lightweight `httpx`-based S3 client for MinIO presigned URL generation (builder may use `boto3` or `minio-py` as standard).
- Visual styling details for the task detail tabs (Tailwind CSS matching the existing clean, professional slate/indigo design system).
