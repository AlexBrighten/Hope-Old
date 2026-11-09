"""
tests/test_hope.py — Comprehensive unit & integration tests for Hope AI Agent.
"""

import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


class TestHopeInfrastructure(unittest.TestCase):
    """Test tools, brain layer, and graceful fallbacks."""

    def test_tools_count(self):
        """Verify all modular tools are registered in ALL_TOOLS."""
        import tools
        self.assertGreaterEqual(len(tools.ALL_TOOLS), 40)
        tool_names = [fn.__name__ for fn in tools.ALL_TOOLS]

        # Verify Core tools
        self.assertIn("search_web", tool_names)
        self.assertIn("current_time", tool_names)
        self.assertIn("remember", tool_names)
        self.assertIn("recall", tool_names)

        # Verify GitHub tools
        self.assertIn("github_list_repos", tool_names)
        self.assertIn("github_read_file", tool_names)
        self.assertIn("github_create_issue", tool_names)
        self.assertIn("github_list_prs", tool_names)

        # Verify Gmail tools
        self.assertIn("gmail_list_messages", tool_names)
        self.assertIn("gmail_read_message", tool_names)
        self.assertIn("gmail_send_email", tool_names)
        self.assertIn("gmail_create_draft", tool_names)

        # Verify Calendar tools
        self.assertIn("calendar_list_events", tool_names)
        self.assertIn("calendar_create_event", tool_names)
        self.assertIn("calendar_update_event", tool_names)

        # Verify Google Docs tools
        self.assertIn("gdocs_create_document", tool_names)
        self.assertIn("gdocs_read_document", tool_names)
        self.assertIn("gdocs_append_text", tool_names)

        # Verify Google Sheets tools
        self.assertIn("gsheets_create_spreadsheet", tool_names)
        self.assertIn("gsheets_read_range", tool_names)
        self.assertIn("gsheets_write_range", tool_names)
        self.assertIn("gsheets_append_rows", tool_names)

        # Verify Browser tools
        self.assertIn("browser_open_and_read", tool_names)
        self.assertIn("browser_take_screenshot", tool_names)

    def test_core_time(self):
        """Test current_time returns formatted date."""
        from tools.core import current_time
        now_str = current_time()
        self.assertTrue(len(now_str) > 10)

    def test_core_memory(self):
        """Test remember and recall functions."""
        from tools.core import remember, recall
        res = remember("Test memory note for Hope")
        self.assertEqual(res, "Remembered.")
        content = recall()
        self.assertIn("Test memory note for Hope", content)

    def test_brain_router(self):
        """Test intent routing logic."""
        from brain.router import route_query, strip_routing_prefix

        # Explicit overrides
        self.assertEqual(route_query("/local summarize this"), "local")
        self.assertEqual(route_query("/gemini check calendar"), "cloud")
        self.assertEqual(strip_routing_prefix("/local hello"), "hello")

        # Heuristic keywords
        self.assertEqual(route_query("Please create a GitHub pull request"), "cloud")
        self.assertEqual(route_query("Check my calendar for tomorrow"), "cloud")
        self.assertEqual(route_query("Search my unread emails in Gmail"), "cloud")
        self.assertEqual(route_query("Hello there, how are you?"), "local")

    def test_github_graceful_unconfigured(self):
        """GitHub functions should return helpful instructions when token is missing."""
        from tools.github_tool import github_list_repos
        res = github_list_repos()
        # Should either list repos (if token present) or return setup instructions
        self.assertTrue("GitHub is not configured" in res or "•" in res or "repos" in res)

    def test_gmail_graceful_unconfigured(self):
        """Gmail functions should return helpful setup instructions when unconfigured."""
        from tools.gmail_tool import gmail_list_messages
        res = gmail_list_messages()
        self.assertTrue("Gmail is not configured" in res or "Messages" in res or "No messages" in res)

    def test_calendar_graceful_unconfigured(self):
        """Calendar functions should return helpful setup instructions when unconfigured."""
        from tools.calendar_tool import calendar_list_events
        res = calendar_list_events()
        self.assertTrue("Google Calendar is not configured" in res or "Events" in res or "No events" in res)

    def test_gdocs_graceful_unconfigured(self):
        """Google Docs functions should return helpful instructions when unconfigured."""
        from tools.gdocs_tool import gdocs_read_document
        res = gdocs_read_document("sample_id")
        self.assertTrue("Google OAuth is not configured" in res or "Error" in res or "Content" in res)

    def test_gsheets_graceful_unconfigured(self):
        """Google Sheets functions should return helpful instructions when unconfigured."""
        from tools.gsheets_tool import gsheets_read_range
        res = gsheets_read_range("sample_id", "A1:B2")
        self.assertTrue("Google OAuth is not configured" in res or "Error" in res or "Range" in res)

    def test_approval_gate(self):
        """Test staging and approving mutating actions."""
        from tools.approval import stage_action, approve_action, reject_action, get_action_status
        act = stage_action("test_action", {"key": "val"}, "Test summary")
        self.assertEqual(get_action_status(act.action_id), "pending")

        # Approve
        ok, msg = approve_action(act.action_id)
        self.assertTrue(ok)
        self.assertEqual(get_action_status(act.action_id), "approved")

        # Reject another
        act2 = stage_action("test_action2", {}, "Test summary 2")
        ok2, msg2 = reject_action(act2.action_id)
        self.assertTrue(ok2)
        self.assertEqual(get_action_status(act2.action_id), "rejected")

    def test_github_webhook_hmac(self):
        """Test GitHub HMAC-SHA256 signature verification."""
        import hmac, hashlib
        from hooks_server import verify_github_signature
        import hooks_server

        # Test with configured secret
        hooks_server.GITHUB_WEBHOOK_SECRET = "secret123"
        payload = b'{"action":"opened"}'
        expected_sig = "sha256=" + hmac.new(b"secret123", payload, hashlib.sha256).hexdigest()

        # Valid signature
        valid, err = verify_github_signature(payload, expected_sig)
        self.assertTrue(valid)

        # Invalid / tampered payload
        valid, err = verify_github_signature(b'{"tampered":true}', expected_sig)
        self.assertFalse(valid)

        # Missing signature
        valid, err = verify_github_signature(payload, None)
        self.assertFalse(valid)

    def test_fastapi_web_endpoints(self):
        """Test Hope FastAPI executive web app endpoints."""
        from fastapi.testclient import TestClient
        from app import app
        client = TestClient(app)

        # 1. Health & status endpoint
        res = client.get("/api/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "online")
        self.assertIn("integrations", data)
        self.assertIn("pending_approvals_count", data)

        # 2. Approvals listing
        res = client.get("/api/approvals")
        self.assertEqual(res.status_code, 200)
        approvals_data = res.json()
        self.assertIn("pending", approvals_data)
        self.assertIn("recent", approvals_data)

        # 3. Long-term memory endpoint
        res = client.get("/api/memory")
        self.assertEqual(res.status_code, 200)
        self.assertIn("content", res.json())

        # 4. PWA Web App Manifest
        res = client.get("/manifest.json")
        self.assertEqual(res.status_code, 200)
        manifest = res.json()
        self.assertIn("Hope", manifest["name"])
        self.assertEqual(manifest["display"], "standalone")

        # 5. Routing config toggle
        res = client.post("/api/config/routing", json={"mode": "auto"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["mode"], "auto")

        # 6. Chat endpoint approval command recognition & persistent history
        res = client.post("/api/chat", json={"message": "/status"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("Status Report", res.json()["reply"])

        # 7. Chat history persistence check
        hist_res = client.get("/api/chat/history")
        self.assertEqual(hist_res.status_code, 200)
        messages = hist_res.json()["messages"]
        self.assertGreaterEqual(len(messages), 2)  # User /status + Agent reply
        self.assertEqual(messages[-2]["content"], "/status")
        self.assertIn("Status Report", messages[-1]["content"])

        # 8. Chat archives listing
        arch_res = client.get("/api/chat/archives")
        self.assertEqual(arch_res.status_code, 200)
        self.assertIn("archives", arch_res.json())



if __name__ == "__main__":
    unittest.main()

