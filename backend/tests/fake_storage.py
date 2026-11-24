"""In-memory stand-in for app.core.storage.R2Storage (tests only)."""
from app.core.storage import StorageError, StorageObjectNotFound


class FakeStorage:
    def __init__(self):
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.fail_upload = self.fail_download = self.fail_delete = False
        self.after_download = None  # optional hook, to simulate races

    def upload_bytes(self, path, data, content_type):
        if self.fail_upload:
            raise StorageError("upload failed")
        self.objects[path] = (bytes(data), content_type)

    def download_bytes(self, path):
        if self.fail_download:
            raise StorageError("download failed")
        if path not in self.objects:
            raise StorageObjectNotFound("missing")
        data = self.objects[path][0]
        if self.after_download:
            self.after_download()
        return data

    def delete(self, path):
        if self.fail_delete:
            raise StorageError("delete failed")
        self.objects.pop(path, None)

    def paths(self, prefix=""):
        return sorted(p for p in self.objects if p.startswith(prefix))
