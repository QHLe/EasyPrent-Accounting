from datetime import datetime, timezone
from typing import Optional
import uuid
from urllib.parse import quote, unquote, urlsplit
from xml.etree import ElementTree
import httpx


class NextcloudService:
    """Minimal CalDAV client for Nextcloud Tasks.

    This client writes VTODO ICS files via WebDAV/CalDAV to a tasks collection.
    Provide a tasks collection base path or rely on a sane default.
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        verify_ssl: bool = True,
        tasks_collection: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        # Default tasks collection under CalDAV calendars; may need adjustment per instance
        default_collection = f"{self.base_url}/remote.php/dav/calendars/{self.username}/personal"
        provided = (tasks_collection or "").strip()
        # If only a DAV root was provided (no '/calendars/' segment), fall back to default
        if not provided or "/calendars/" not in provided:
            self.tasks_collection = default_collection.rstrip("/")
        else:
            self.tasks_collection = provided.rstrip("/")

    @staticmethod
    def _format_ics_datetime(value: datetime | None = None) -> str:
        dt = value or datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y%m%dT%H%M%SZ")

    def _client(self, timeout: int | float = 10) -> httpx.Client:
        return httpx.Client(
            auth=(self.username, self.password),
            verify=self.verify_ssl,
            timeout=timeout,
            follow_redirects=True,
        )

    def _status_to_ics(self, status: Optional[str]) -> Optional[str]:
        if status is None:
            return None
        s = str(status).lower()
        if s == "done":
            return "COMPLETED"
        # Map both open/due to NEEDS-ACTION for simplicity
        return "NEEDS-ACTION"

    def _build_vtodo_ics(
        self,
        uid: str,
        title: str,
        status: Optional[str],
        recurrence_rule: Optional[str],
        description: Optional[str] = None,
        due_date: Optional[str] = None,
    ) -> str:
        ics_lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//simple_cms//EN",
            "BEGIN:VTODO",
            f"UID:{uid}",
            f"DTSTAMP:{self._format_ics_datetime()}",
            f"LAST-MODIFIED:{self._format_ics_datetime()}",
            f"SUMMARY:{title}",
        ]
        ics_status = self._status_to_ics(status)
        if ics_status:
            ics_lines.append(f"STATUS:{ics_status}")
        if recurrence_rule:
            ics_lines.append(f"RRULE:{recurrence_rule}")
        if description:
            ics_lines.append(f"DESCRIPTION:{description}")
        if due_date:
            # Expecting ISO date YYYY-MM-DD; express as DATE (not DATE-TIME)
            dd = due_date.strip()
            if len(dd) == 10 and dd[4] == "-" and dd[7] == "-":
                ymd = dd.replace("-", "")
                ics_lines.append(f"DUE;VALUE=DATE:{ymd}")
        ics_lines.extend([
            "END:VTODO",
            "END:VCALENDAR",
        ])
        return "\r\n".join(ics_lines) + "\r\n"

    def _put_ics(self, path: str, ics: str) -> None:
        headers = {"Content-Type": "text/calendar"}
        last_status = None
        last_body = None
        # Simple retry loop
        for attempt in range(3):
            with self._client(timeout=10) as client:
                resp = client.put(path, content=ics.encode("utf-8"), headers=headers)
                if resp.status_code in (200, 201, 204):
                    return
                last_status = resp.status_code
                try:
                    last_body = resp.text[:300]
                except Exception:
                    last_body = None
        raise RuntimeError(f"Nextcloud CalDAV PUT failed for {path} (status={last_status}, body={last_body})")

    @property
    def backup_directory(self) -> str:
        return f"{self.base_url}/remote.php/dav/files/{quote(self.username, safe='')}/easy_contract_manager/backups"

    def _ensure_webdav_collection(self, path: str) -> None:
        last_status = None
        last_body = None
        with self._client(timeout=10) as client:
            segments = [segment for segment in path.split("/") if segment]
            if len(segments) < 2:
                raise RuntimeError(f"Invalid Nextcloud backup path: {path}")

            current = f"{self.base_url}/{segments[0]}/{segments[1]}"
            for segment in segments[2:]:
                current = f"{current}/{quote(segment, safe='')}"
                resp = client.request("MKCOL", current)
                if resp.status_code in (201, 405):
                    continue
                if resp.status_code == 409:
                    raise RuntimeError(f"Nextcloud backup folder missing parent for {current}")
                if resp.status_code >= 400:
                    last_status = resp.status_code
                    try:
                        last_body = resp.text[:300]
                    except Exception:
                        last_body = None
                    raise RuntimeError(
                        f"Nextcloud MKCOL failed for {current} (status={last_status}, body={last_body})"
                    )

    def upload_backup(self, filename: str, content: bytes, backup_directory: Optional[str] = None) -> str:
        target_directory = (backup_directory or self.backup_directory).rstrip("/")
        if not target_directory.startswith(self.base_url):
            raise RuntimeError("Nextcloud backup path must stay within the configured instance")

        relative_directory = target_directory[len(self.base_url):].lstrip("/")
        self._ensure_webdav_collection(relative_directory)

        target_path = f"{target_directory}/{quote(filename, safe='')}"
        last_status = None
        last_body = None
        headers = {"Content-Type": "application/json"}
        for _attempt in range(3):
            with self._client(timeout=15) as client:
                resp = client.put(target_path, content=content, headers=headers)
                if resp.status_code in (200, 201, 204):
                    return target_path
                last_status = resp.status_code
                try:
                    last_body = resp.text[:300]
                except Exception:
                    last_body = None
        raise RuntimeError(
            f"Nextcloud backup upload failed for {target_path} (status={last_status}, body={last_body})"
        )

    def list_backups(self, backup_directory: Optional[str] = None) -> list[dict[str, str]]:
        target_directory = (backup_directory or self.backup_directory).rstrip("/")
        headers = {"Depth": "1"}
        with self._client(timeout=15) as client:
            resp = client.request("PROPFIND", target_directory, headers=headers)
            if resp.status_code not in (200, 207):
                body = None
                try:
                    body = resp.text[:300]
                except Exception:
                    body = None
                raise RuntimeError(
                    f"Nextcloud backup listing failed for {target_directory} (status={resp.status_code}, body={body})"
                )

        try:
            root = ElementTree.fromstring(resp.text)
        except ElementTree.ParseError as exc:
            raise RuntimeError(f"Nextcloud backup listing parse failed: {exc}") from exc

        namespace = {"d": "DAV:"}
        items: list[dict[str, str]] = []
        base_path = unquote(urlsplit(target_directory).path).rstrip("/")
        for response in root.findall("d:response", namespace):
            href = response.findtext("d:href", default="", namespaces=namespace)
            if not href:
                continue
            decoded_path = unquote(urlsplit(href).path).rstrip("/")
            if decoded_path == base_path:
                continue
            name = decoded_path.split("/")[-1]
            if not name.lower().endswith(".json"):
                continue
            items.append({
                "name": name,
                "remote_path": f"{target_directory}/{quote(name, safe='')}",
            })

        items.sort(key=lambda item: item["name"], reverse=True)
        return items

    def download_backup(self, filename: str, backup_directory: Optional[str] = None) -> bytes:
        normalized_name = (filename or "").strip()
        if not normalized_name:
            raise RuntimeError("Backup filename is required")

        target_directory = (backup_directory or self.backup_directory).rstrip("/")
        target_path = f"{target_directory}/{quote(normalized_name, safe='')}"
        with self._client(timeout=20) as client:
            resp = client.get(target_path)
            if resp.status_code != 200:
                body = None
                try:
                    body = resp.text[:300]
                except Exception:
                    body = None
                raise RuntimeError(
                    f"Nextcloud backup download failed for {target_path} (status={resp.status_code}, body={body})"
                )
            return resp.content

    def test_connection(self) -> None:
        headers = {"Depth": "0"}
        url = self.tasks_collection
        with self._client(timeout=10) as client:
            resp = client.request("PROPFIND", url, headers=headers)
            if resp.status_code not in (200, 207):
                body = None
                try:
                    body = resp.text[:300]
                except Exception:
                    body = None
                raise RuntimeError(
                    f"Nextcloud connection failed for {url} (status={resp.status_code}, body={body})"
                )

    def _get_ics(self, path: str) -> str:
        with self._client(timeout=10) as client:
            resp = client.get(path, headers={"Accept": "text/calendar"})
            if resp.status_code != 200:
                body = None
                try:
                    body = resp.text[:300]
                except Exception:
                    body = None
                raise RuntimeError(f"Nextcloud CalDAV GET failed for {path} (status={resp.status_code}, body={body})")
            return resp.text

    @staticmethod
    def _unfold_ics_lines(ics: str) -> list[str]:
        lines: list[str] = []
        for raw_line in ics.splitlines():
            if raw_line.startswith((" ", "\t")) and lines:
                lines[-1] += raw_line[1:]
            else:
                lines.append(raw_line)
        return lines

    @staticmethod
    def _parse_ics_date(value: str) -> Optional[str]:
        trimmed = value.strip()
        if len(trimmed) == 8 and trimmed.isdigit():
            return f"{trimmed[0:4]}-{trimmed[4:6]}-{trimmed[6:8]}"
        return None

    @staticmethod
    def _parse_ics_datetime(value: str) -> Optional[datetime]:
        trimmed = value.strip()
        if not trimmed:
            return None
        for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S"):
            try:
                parsed = datetime.strptime(trimmed, fmt)
                return parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    def fetch_task(self, nextcloud_id: str) -> dict[str, Optional[str] | datetime]:
        if not nextcloud_id:
            raise ValueError("nextcloud_id required for fetch_task")
        resource = f"{self.tasks_collection}/{nextcloud_id}.ics"
        ics = self._get_ics(resource)
        fields: dict[str, Optional[str]] = {
            "title": None,
            "status": None,
            "recurrence_rule": None,
            "description": None,
            "due_date": None,
            "modified_at": None,
        }
        for line in self._unfold_ics_lines(ics):
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            if key == "SUMMARY":
                fields["title"] = value
            elif key == "STATUS":
                normalized = value.strip().upper()
                fields["status"] = "done" if normalized == "COMPLETED" else "open"
            elif key == "RRULE":
                fields["recurrence_rule"] = value or None
            elif key == "DESCRIPTION":
                fields["description"] = value or None
            elif key.startswith("DUE"):
                fields["due_date"] = self._parse_ics_date(value)
            elif key in {"LAST-MODIFIED", "DTSTAMP"} and fields["modified_at"] is None:
                fields["modified_at"] = self._parse_ics_datetime(value)
        return fields

    def create_task(self, title: str, status: str, recurrence_rule: Optional[str] = None, description: Optional[str] = None, due_date: Optional[str] = None) -> str:
        uid = f"simplecms-{uuid.uuid4().hex}"
        # Resource path under the collection
        resource = f"{self.tasks_collection}/{uid}.ics"
        ics = self._build_vtodo_ics(uid=uid, title=title, status=status, recurrence_rule=recurrence_rule, description=description, due_date=due_date)
        self._put_ics(resource, ics)
        return uid

    def update_task(
        self,
        nextcloud_id: str,
        title: Optional[str] = None,
        status: Optional[str] = None,
        recurrence_rule: Optional[str] = None,
        description: Optional[str] = None,
        due_date: Optional[str] = None,
    ) -> None:
        if not nextcloud_id:
            raise ValueError("nextcloud_id required for update_task")
        # Use existing id as UID
        uid = nextcloud_id
        resource = f"{self.tasks_collection}/{uid}.ics"
        # Fallbacks: keep minimal ICS if no fields provided
        ics = self._build_vtodo_ics(uid=uid, title=title or "", status=status, recurrence_rule=recurrence_rule, description=description, due_date=due_date)
        self._put_ics(resource, ics)
