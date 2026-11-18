import os
import unittest
from unittest.mock import patch, MagicMock

# Use SQLite for standalone automated endpoint testing
os.environ["DATABASE_URL"] = "sqlite:///./test_taskbot.db"

from fastapi.testclient import TestClient
from database import Base, engine, SessionLocal, Conversation, Message, Task, SubTask
from main import app
import agent

class TestTaskPilotFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)
        if os.path.exists("test_taskbot.db"):
            os.remove("test_taskbot.db")

    def setUp(self):
        # Clear tables between tests
        db = SessionLocal()
        db.query(Message).delete()
        db.query(SubTask).delete()
        db.query(Task).delete()
        db.query(Conversation).delete()
        db.commit()
        db.close()

    def test_health_check(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("status"), "ok")

    def test_create_and_list_tasks_with_and_without_subtasks(self):
        # 1. Create simple task without subtasks
        res1 = self.client.post("/tasks", json={
            "title": "Buy groceries",
            "priority": "low"
        })
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1["title"], "Buy groceries")
        self.assertEqual(data1["subtasks"], [])

        # 2. Create complex task with subtasks
        res2 = self.client.post("/tasks", json={
            "title": "Launch Website",
            "description": "Deploy to production",
            "priority": "high",
            "subtasks": [
                {"title": "Design landing page"},
                {"title": "Set up database"},
                {"title": "Configure custom domain"}
            ]
        })
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2["title"], "Launch Website")
        self.assertEqual(len(data2["subtasks"]), 3)
        self.assertEqual(data2["subtasks"][0]["title"], "Design landing page")
        self.assertEqual(data2["subtasks"][0]["status"], "todo")

        # 3. List tasks
        res_list = self.client.get("/tasks")
        self.assertEqual(res_list.status_code, 200)
        tasks = res_list.json()
        self.assertEqual(len(tasks), 2)
        # Should be ordered desc by id
        self.assertEqual(tasks[0]["title"], "Launch Website")
        self.assertEqual(len(tasks[0]["subtasks"]), 3)
        self.assertEqual(tasks[1]["title"], "Buy groceries")
        self.assertEqual(len(tasks[1]["subtasks"]), 0)

    def test_toggle_task_without_subtasks(self):
        res_create = self.client.post("/tasks", json={"title": "Simple todo"})
        task_id = res_create.json()["id"]

        # Directly toggle todo -> done
        res1 = self.client.patch(f"/tasks/{task_id}/toggle")
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json()["status"], "done")

        # Directly toggle done -> todo
        res2 = self.client.patch(f"/tasks/{task_id}/toggle")
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["status"], "todo")

    def test_prevent_direct_complete_when_task_has_incomplete_subtasks(self):
        # Create task with 2 subtasks
        res_create = self.client.post("/tasks", json={
            "title": "Clean apartment",
            "subtasks": ["Vacuum living room", "Wash dishes"]
        })
        task_id = res_create.json()["id"]

        # Attempt to mark parent task directly as complete
        res_toggle = self.client.patch(f"/tasks/{task_id}/toggle")
        self.assertEqual(res_toggle.status_code, 400)
        self.assertIn("incomplete subtasks", res_toggle.json()["detail"])

        # Check that task status is still todo
        res_get = self.client.get("/tasks")
        self.assertEqual(res_get.json()[0]["status"], "todo")

    def test_complete_all_subtasks_auto_completes_parent_task(self):
        # Create task with 2 subtasks
        res_create = self.client.post("/tasks", json={
            "title": "Prepare presentation",
            "subtasks": ["Draft slides", "Practice speech"]
        })
        task_data = res_create.json()
        task_id = task_data["id"]
        subtask1_id = task_data["subtasks"][0]["id"]
        subtask2_id = task_data["subtasks"][1]["id"]

        # 1. Complete subtask 1
        res_st1 = self.client.patch(f"/subtasks/{subtask1_id}/toggle")
        self.assertEqual(res_st1.status_code, 200)
        task_state1 = res_st1.json()
        self.assertEqual(task_state1["status"], "todo") # Still todo because subtask 2 is unfinished

        # 2. Complete subtask 2 (all subtasks are now done!)
        res_st2 = self.client.patch(f"/subtasks/{subtask2_id}/toggle")
        self.assertEqual(res_st2.status_code, 200)
        task_state2 = res_st2.json()
        # Parent task is automatically marked done!
        self.assertEqual(task_state2["status"], "done")

        # 3. Uncheck subtask 1 -> Parent task should automatically return to todo
        res_st3 = self.client.patch(f"/subtasks/{subtask1_id}/toggle")
        self.assertEqual(res_st3.status_code, 200)
        task_state3 = res_st3.json()
        self.assertEqual(task_state3["status"], "todo")

    @patch("agent.client")
    def test_chat_normal_message_no_tools(self, mock_openai):
        mock_choice = MagicMock()
        mock_choice.message.tool_calls = None
        mock_choice.message.content = "Hello! I can help you plan and manage your tasks. What's on your agenda today?"
        
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.return_value = mock_resp
        agent.client = mock_client_instance

        res = self.client.post("/chat", json={"message": "hi"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["reply"], "Hello! I can help you plan and manage your tasks. What's on your agenda today?")
        self.assertEqual(data["suggested_tasks"], [])

    @patch("agent.client")
    def test_chat_suggest_tasks_with_subtasks(self, mock_openai):
        # Mock LLM calling suggest_tasks tool with subtasks
        tool_call_mock = MagicMock()
        tool_call_mock.function.arguments = '''{
            "tasks": [
                {
                    "title": "Renew passport",
                    "description": "Get passport ready for international travel",
                    "priority": "high",
                    "subtasks": [
                        {"title": "Take passport photos"},
                        {"title": "Fill out renewal form"},
                        {"title": "Submit application to passport agency"}
                    ]
                }
            ]
        }'''
        mock_choice = MagicMock()
        mock_choice.message.tool_calls = [tool_call_mock]
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.return_value = mock_resp
        agent.client = mock_client_instance

        res = self.client.post("/chat", json={"message": "I need to renew my passport"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["suggested_tasks"]), 1)
        suggested = data["suggested_tasks"][0]
        self.assertEqual(suggested["title"], "Renew passport")
        self.assertEqual(len(suggested["subtasks"]), 3)

        # Add the suggested task with subtasks into the database
        res_add = self.client.post("/tasks", json=suggested)
        self.assertEqual(res_add.status_code, 200)
        added_task = res_add.json()
        self.assertEqual(added_task["title"], "Renew passport")
        self.assertEqual(len(added_task["subtasks"]), 3)

    @patch("agent.client")
    def test_duplicate_task_not_suggested_if_already_added(self, mock_openai):
        self.client.post("/tasks", json={"title": "Renew passport", "priority": "high"})

        tool_call_mock = MagicMock()
        tool_call_mock.function.arguments = '''{
            "tasks": [
                {"title": "Renew passport", "priority": "high"},
                {"title": "Book hotel", "priority": "medium"}
            ]
        }'''
        mock_choice = MagicMock()
        mock_choice.message.tool_calls = [tool_call_mock]
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.return_value = mock_resp
        agent.client = mock_client_instance

        res = self.client.post("/chat", json={"message": "I need to renew passport and book hotel"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        suggested = data["suggested_tasks"]
        self.assertEqual(len(suggested), 1)
        self.assertEqual(suggested[0]["title"], "Book hotel")

if __name__ == "__main__":
    unittest.main()
