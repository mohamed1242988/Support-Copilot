import pathlib
import tempfile
import unittest

from storage import database


class SearchRankingTests(unittest.TestCase):
    def setUp(self):
        self.original_database_path = database.DATABASE_PATH
        self.temp_directory = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = pathlib.Path(self.temp_directory.name) / "test.db"
        database.initialize_database()

    def tearDown(self):
        database.DATABASE_PATH = self.original_database_path
        self.temp_directory.cleanup()

    def test_freshdesk_prefers_bm25_relevance_over_recency(self):
        database.save_ticket(self._ticket(1, "database backup failure", "2026-01-01"))
        database.save_ticket(self._ticket(2, "database question", "2026-02-01"))

        results = database.search_local_tickets("database backup failure")

        self.assertEqual([result["id"] for result in results], [1, 2])

    def test_jira_prefers_bm25_relevance_over_recency(self):
        database.save_jira_issue(self._issue("SUP-1", "database backup failure", "2026-01-01"))
        database.save_jira_issue(self._issue("SUP-2", "database question", "2026-02-01"))

        results = database.search_local_jira("database backup failure")

        self.assertEqual([result["key"] for result in results], ["SUP-1", "SUP-2"])

    @staticmethod
    def _ticket(ticket_id, subject, updated_at):
        return {
            "id": ticket_id,
            "subject": subject,
            "description_text": subject,
            "status": 2,
            "priority": 1,
            "created_at": updated_at,
            "updated_at": updated_at,
        }

    @staticmethod
    def _issue(key, summary, updated_at):
        return {
            "key": key,
            "project": "SUP",
            "summary": summary,
            "description": summary,
            "status": "Open",
            "created_at": updated_at,
            "updated_at": updated_at,
        }
