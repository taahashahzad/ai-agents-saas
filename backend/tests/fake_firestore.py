"""Minimal in-memory stand-in for google.cloud.firestore.Client, used ONLY by tests.

It implements just the surface the services use: collection/document/subcollection,
get/set/create/update, batch (applied atomically on commit), collection_group().where(filter=...)
and get_all(). The application itself always talks to real Cloud Firestore.
"""
import copy
import uuid

from google.api_core.exceptions import AlreadyExists, NotFound


class FakeSnapshot:
    def __init__(self, ref, data):
        self.reference = ref
        self.id = ref.id
        self._data = data

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return copy.deepcopy(self._data) if self._data is not None else None


class FakeDocumentReference:
    def __init__(self, db, path):
        self._db, self.path = db, path

    def __eq__(self, other):
        return isinstance(other, FakeDocumentReference) and other.path == self.path

    def __hash__(self):
        return hash(self.path)

    @property
    def id(self):
        return self.path.split("/")[-1]

    @property
    def parent(self):
        return FakeCollectionReference(self._db, self.path.rsplit("/", 1)[0])

    def collection(self, name):
        return FakeCollectionReference(self._db, f"{self.path}/{name}")

    def get(self, transaction=None):
        return FakeSnapshot(self, self._db.docs.get(self.path))

    def set(self, data, merge=False):
        self._db._set(self.path, data)

    def create(self, data):
        self._db._create(self.path, data)

    def update(self, data):
        self._db._update(self.path, data)

    def delete(self):
        self._db.docs.pop(self.path, None)


class FakeQuery:
    def __init__(self, db, matcher, filters=(), orders=(), limit_count=None):
        self._db, self._matcher, self._filters = db, matcher, filters
        self._orders, self._limit_count = orders, limit_count

    def where(self, *args, filter=None, **kwargs):
        assert filter is not None, "fake supports where(filter=FieldFilter(...)) only"
        return FakeQuery(
            self._db, self._matcher, self._filters + (filter,), self._orders, self._limit_count
        )

    def order_by(self, field_path, direction=None):
        return FakeQuery(
            self._db,
            self._matcher,
            self._filters,
            self._orders + ((field_path, direction),),
            self._limit_count,
        )

    def limit(self, count):
        return FakeQuery(self._db, self._matcher, self._filters, self._orders, count)

    def get(self, transaction=None):
        return list(self.stream())

    def stream(self, transaction=None):
        matches = [
            (path, data)
            for path, data in list(self._db.docs.items())
            if self._matcher(path) and all(self._ok(f, data) for f in self._filters)
        ]
        for field_path, direction in reversed(self._orders):
            matches.sort(
                key=lambda item: item[1].get(field_path),
                reverse=str(direction).upper().endswith("DESCENDING"),
            )
        if self._limit_count is not None:
            matches = matches[:self._limit_count]
        for path, data in matches:
            yield FakeSnapshot(FakeDocumentReference(self._db, path), data)

    @staticmethod
    def _ok(f, data):
        assert f.op_string == "==", "fake supports '==' only"
        return data.get(f.field_path) == f.value


class FakeCollectionReference(FakeQuery):
    def __init__(self, db, path):
        self.path = path
        prefix, depth = path + "/", path.count("/") + 1
        super().__init__(db, lambda p: p.startswith(prefix) and p.count("/") == depth)

    @property
    def id(self):
        return self.path.split("/")[-1]

    @property
    def parent(self):
        return None if "/" not in self.path else FakeDocumentReference(self._db, self.path.rsplit("/", 1)[0])

    def document(self, doc_id=None):
        return FakeDocumentReference(self._db, f"{self.path}/{doc_id or uuid.uuid4().hex[:20]}")


class FakeBatch:
    def __init__(self, db):
        self._db, self._ops = db, []

    def set(self, ref, data):
        self._ops.append(("set", ref.path, data))

    def update(self, ref, data):
        self._ops.append(("update", ref.path, data))

    def delete(self, ref):
        self._ops.append(("delete", ref.path, None))

    def commit(self):
        snapshot = copy.deepcopy(self._db.docs)
        try:
            for op, path, data in self._ops:
                if op == "delete":
                    self._db.docs.pop(path, None)
                else:
                    getattr(self._db, f"_{op}")(path, data)
        except Exception:
            self._db.docs = snapshot  # all-or-nothing
            raise
        self._ops = []


class FakeTransaction:
    """Applies writes immediately (tests are single-threaded). The services read first,
    then write, so this behaves like a committed Firestore transaction."""

    def __init__(self, db):
        self._db = db

    def set(self, ref, data):
        self._db._set(ref.path, data)

    def create(self, ref, data):
        self._db._create(ref.path, data)

    def update(self, ref, data):
        self._db._update(ref.path, data)

    def delete(self, ref):
        self._db.docs.pop(ref.path, None)


class FakeFirestore:
    def __init__(self):
        self.docs: dict[str, dict] = {}

    def _set(self, path, data):
        self.docs[path] = copy.deepcopy(data)

    def _create(self, path, data):
        if path in self.docs:
            raise AlreadyExists("document already exists")
        self._set(path, data)

    def _update(self, path, data):
        if path not in self.docs:
            raise NotFound("document not found")
        self.docs[path].update(copy.deepcopy(data))

    def collection(self, name):
        return FakeCollectionReference(self, name)

    def collection_group(self, name):
        def matcher(path):
            parts = path.split("/")
            return len(parts) % 2 == 0 and parts[-2] == name
        return FakeQuery(self, matcher)

    def batch(self):
        return FakeBatch(self)

    def transaction(self):
        return FakeTransaction(self)

    def get_all(self, refs):
        for ref in refs:
            yield ref.get()
