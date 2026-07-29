import json
import os
from urllib.request import Request, urlopen


class SupabaseStorageDeletion:
    """worker-only service-role로 memories 버킷의 사용자 prefix를 지운다."""

    bucket = "memories"

    def __init__(
        self,
        base_url: str | None = None,
        service_role_key: str | None = None,
    ):
        project_url = base_url or os.environ.get("SUPABASE_URL")
        key = service_role_key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not project_url or not key:
            raise RuntimeError("storage_credentials_missing")
        self.url = f"{project_url.rstrip('/')}/storage/v1"
        self.headers = {
            "apikey": key,
            "authorization": f"Bearer {key}",
            "content-type": "application/json",
        }

    def delete_user_objects(self, user_id: str) -> None:
        paths = self._list_paths(user_id)
        for offset in range(0, len(paths), 1000):
            self._request(
                "DELETE",
                f"/object/{self.bucket}",
                {"prefixes": paths[offset : offset + 1000]},
            )

    def has_user_objects(self, user_id: str) -> bool:
        return bool(self._list_paths(user_id))

    def _list_paths(self, prefix: str) -> list[str]:
        paths: list[str] = []
        offset = 0
        while True:
            items = self._request(
                "POST",
                f"/object/list/{self.bucket}",
                {
                    "prefix": prefix,
                    "limit": 1000,
                    "offset": offset,
                    "sortBy": {"column": "name", "order": "asc"},
                },
            )
            if not isinstance(items, list):
                raise RuntimeError("storage_list_invalid")
            for item in items:
                name = item.get("name") if isinstance(item, dict) else None
                if not isinstance(name, str) or not name:
                    continue
                path = f"{prefix}/{name}"
                if not path.startswith(f"{prefix.split('/')[0]}/"):
                    raise RuntimeError("storage_prefix_violation")
                if item.get("id"):
                    paths.append(path)
                else:
                    paths.extend(self._list_paths(path))
            if len(items) < 1000:
                break
            offset += len(items)
        return paths

    def _request(self, method: str, path: str, body: dict):
        payload = json.dumps(body).encode("utf-8")
        request = Request(
            f"{self.url}{path}",
            data=payload,
            headers=self.headers,
            method=method,
        )
        with urlopen(request, timeout=20) as response:
            raw = response.read()
        return json.loads(raw.decode("utf-8")) if raw else None
