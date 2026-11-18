import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_task_creation_and_numbering(client: AsyncClient, setup_orgs):
    tokens = setup_orgs["tokens"]

    # 1. Create Project
    res_proj = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"name": "Flight App", "key": "FLT"},
    )
    assert res_proj.status_code == 201
    proj_id = res_proj.json()["id"]

    # 2. Create Task 1
    res_t1 = await client.post(
        f"/api/v1/projects/{proj_id}/tasks",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"title": "Design Booking Flow", "priority": "high"},
    )
    assert res_t1.status_code == 201
    t1 = res_t1.json()
    assert t1["task_number"] == 1
    assert t1["task_code"] == "FLT-1"

    # 3. Create Task 2 with embedded subtasks
    res_t2 = await client.post(
        f"/api/v1/projects/{proj_id}/tasks",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={
            "title": "Backend API Setup",
            "priority": "critical",
            "subtasks": [
                {"title": "Setup PostgreSQL schema"},
                {"title": "Configure authentication"},
            ],
        },
    )
    assert res_t2.status_code == 201
    t2 = res_t2.json()
    assert t2["task_number"] == 2
    assert t2["task_code"] == "FLT-2"
    assert len(t2["subtasks"]) == 2
    assert t2["subtasks"][0]["task_number"] == 3
    assert t2["subtasks"][1]["task_number"] == 4


@pytest.mark.asyncio
async def test_subtasks_guardrails_and_autocompletion(client: AsyncClient, setup_orgs):
    tokens = setup_orgs["tokens"]

    # Create project
    res_proj = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"name": "Hotel Ops", "key": "HOTEL"},
    )
    proj_id = res_proj.json()["id"]

    # Create parent task with 2 subtasks
    res_task = await client.post(
        f"/api/v1/projects/{proj_id}/tasks",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={
            "title": "Room Inspection Procedure",
            "subtasks": [
                {"title": "Inspect linen cleanliness"},
                {"title": "Check mini-bar stock"},
            ],
        },
    )
    task = res_task.json()
    parent_id = task["id"]
    sub1_id = task["subtasks"][0]["id"]
    sub2_id = task["subtasks"][1]["id"]

    # Guardrail Check: Attempt to mark parent task as 'done' while subtasks are incomplete
    res_premature = await client.patch(
        f"/api/v1/tasks/{parent_id}/status",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"status": "done"},
    )
    assert res_premature.status_code == 400
    assert res_premature.json()["error"]["code"] == "INCOMPLETE_SUBTASKS"

    # Mark subtask 1 as done
    res_s1 = await client.patch(
        f"/api/v1/tasks/{sub1_id}/status",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"status": "done"},
    )
    assert res_s1.status_code == 200

    # Parent should still be 'todo'
    res_p_check = await client.get(
        f"/api/v1/tasks/{parent_id}",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_p_check.json()["status"] == "todo"

    # Mark subtask 2 as done -> All subtasks are now done!
    res_s2 = await client.patch(
        f"/api/v1/tasks/{sub2_id}/status",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
        json={"status": "done"},
    )
    assert res_s2.status_code == 200

    # Auto-completion verification: Parent task must now automatically be 'done'
    res_parent_done = await client.get(
        f"/api/v1/tasks/{parent_id}",
        headers={"Authorization": f"Bearer {tokens['owner_a']}"},
    )
    assert res_parent_done.json()["status"] == "done"
