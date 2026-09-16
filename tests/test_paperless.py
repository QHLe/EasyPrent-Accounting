from __future__ import annotations

import unittest

from easyprent_accounting.integrations.paperless import UrllibPaperlessAdapter


class _Response:
    def __init__(self, *, status: int = 200, body: bytes = b"", headers: dict[str, str] | None = None) -> None:
        self.status = status
        self.body = body
        self.headers = headers or {}

    def read(self) -> bytes:
        return self.body

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class PaperlessAdapterTests(unittest.TestCase):
    def test_status_checks_document_types_with_token_and_short_timeout(self) -> None:
        requests: list[tuple[object, int]] = []

        def open_url(request, timeout):
            requests.append((request, timeout))
            return _Response()

        adapter = UrllibPaperlessAdapter(opener=open_url)

        self.assertEqual(
            adapter.check_reachability("https://paperless.example.org/", "secret"),
            (True, "Paperless Server erreichbar."),
        )
        request, timeout = requests[0]
        self.assertEqual(request.full_url, "https://paperless.example.org/api/document_types/?page_size=1")
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("Authorization"), "Token secret")
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertEqual(timeout, 5)

    def test_upload_sends_multipart_content_and_returns_document_reference(self) -> None:
        requests: list[tuple[object, int]] = []

        def open_url(request, timeout):
            requests.append((request, timeout))
            return _Response(body=b'{"document_id": 7002}')

        adapter = UrllibPaperlessAdapter(opener=open_url)

        self.assertEqual(
            adapter.upload_document(
                "https://paperless.example.org/", "secret", 'invoice".pdf', "application/pdf", b"PDF contents"
            ),
            {
                "upload_status": "paperless_uploaded",
                "paperless_document_id": "7002",
                "paperless_task_id": None,
                "paperless_reference_url": "https://paperless.example.org/documents/7002/details/",
                "upload_error": None,
            },
        )
        request, timeout = requests[0]
        self.assertEqual(request.full_url, "https://paperless.example.org/api/documents/post_document/")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Token secret")
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertIn("multipart/form-data; boundary=", request.get_header("Content-type"))
        self.assertIn(b'name="document"; filename="invoice_.pdf"', request.data)
        self.assertIn(b"Content-Type: application/pdf", request.data)
        self.assertIn(b"PDF contents", request.data)
        self.assertEqual(timeout, 15)


if __name__ == "__main__":
    unittest.main()
