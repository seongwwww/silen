import json

from silen_worker.deletion import storage as storage_module
from silen_worker.deletion.storage import SupabaseStorageDeletion


class Response:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return self.payload


def test_사용자_prefix를_재귀_조회하고_API로만_삭제한다(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        body = json.loads(request.data)
        if request.get_method() == "DELETE":
            return Response([])
        if body["prefix"] == "user-1":
            return Response(
                [
                    {"name": "a.jpg", "id": "object-1"},
                    {"name": "nested", "id": None},
                ]
            )
        return Response([{"name": "b.jpg", "id": "object-2"}])

    monkeypatch.setattr(storage_module, "urlopen", fake_urlopen)
    storage = SupabaseStorageDeletion("http://storage.test", "service-secret")

    storage.delete_user_objects("user-1")

    delete_request = next(
        request for request, _timeout in requests
        if request.get_method() == "DELETE"
    )
    assert json.loads(delete_request.data) == {
        "prefixes": ["user-1/a.jpg", "user-1/nested/b.jpg"]
    }
    assert "/storage/v1/object/memories" in delete_request.full_url


def test_잔존_검증은_사용자_prefix_밖을_조회하지_않는다(monkeypatch):
    prefixes = []

    def fake_urlopen(request, timeout):
        body = json.loads(request.data)
        prefixes.append(body["prefix"])
        return Response([])

    monkeypatch.setattr(storage_module, "urlopen", fake_urlopen)
    storage = SupabaseStorageDeletion("http://storage.test", "service-secret")

    assert not storage.has_user_objects("user-1")
    assert prefixes == ["user-1"]
