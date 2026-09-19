"""Contract tests for OpenAPI schema generation."""

from __future__ import annotations

import unittest
from fastapi.testclient import TestClient

from easyprent_accounting.asgi import create_asgi_app
from easyprent_accounting.config import AppConfig, SenderAddress
from tests.support import temporary_database


class OpenApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = self.enterContext(temporary_database())
        config = AppConfig(
            db_path=self.database.path,
            project_root=self.database.path.parent,
            sender=SenderAddress(),
        )
        self.app = create_asgi_app(config)
        self.client = TestClient(self.app)

    def test_openapi_schema_contains_expected_operations(self) -> None:
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        schema = response.json()
        
        self.assertIn("paths", schema)
        paths = schema["paths"]
        
        # Check some key routes
        self.assertIn("/api/v1/health", paths)
        self.assertIn("/api/v1/depreciation/assets", paths)
        self.assertIn("/api/v1/dashboard/summary", paths)
        
        # Collect all operation IDs and ensure they follow the expected pattern
        operation_ids = []
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                self.assertIn("operationId", operation, f"Missing operationId for {method.upper()} {path}")
                op_id = operation["operationId"]
                operation_ids.append(op_id)
                self.assertIn("tags", operation, f"Missing tags for {method.upper()} {path}")
                tag = operation["tags"][0].lower().replace(" ", "_")
                
                # Check that our unique ID generator was used (unless overridden)
                # For routes we didn't explicitly override, it should start with tag_
                if op_id not in ("create_depreciation_asset", "list_depreciation_assets", "get_depreciation_schedule", "get_dashboard_summary"):
                    self.assertTrue(op_id.startswith(f"{tag}_"), f"Operation ID {op_id} does not start with tag {tag}_")

        # Ensure there are no duplicate operation IDs
        self.assertEqual(len(operation_ids), len(set(operation_ids)), "Duplicate operation IDs found")

        # Check specific operation IDs are present
        self.assertIn("get_dashboard_summary", operation_ids)

if __name__ == "__main__":
    unittest.main()
