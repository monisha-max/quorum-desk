"""The record store against Firestore's query rules, which the local store does not enforce."""

from google.api_core.exceptions import FailedPrecondition

from quorum import store


class _Snap:
    def __init__(self, doc: dict) -> None:
        self._doc = doc

    def to_dict(self) -> dict:
        return dict(self._doc)


class _Query:
    """Enough of a Firestore query to refuse what Firestore refuses without a composite index."""

    def __init__(self, docs: list[dict], filters=(), order=None, cap=None) -> None:
        self.docs, self.filters, self.order, self.cap = docs, filters, order, cap

    def where(self, filter):
        return _Query(self.docs, (*self.filters, filter), self.order, self.cap)

    def order_by(self, field, direction=None):
        return _Query(self.docs, self.filters, (field, direction), self.cap)

    def limit(self, n):
        return _Query(self.docs, self.filters, self.order, n)

    def stream(self):
        if self.order and any(f.field_path != self.order[0] for f in self.filters):
            raise FailedPrecondition("The query requires an index.")
        rows = [doc for doc in self.docs if all(doc[f.field_path] == f.value for f in self.filters)]
        if self.order:
            rows.sort(key=lambda doc: doc[self.order[0]], reverse=self.order[1] == "DESCENDING")
        return [_Snap(doc) for doc in rows[: self.cap]]


class _Client:
    def __init__(self, docs: list[dict]) -> None:
        self.docs = docs

    def collection(self, name):
        return _Query(self.docs)


def test_one_file_s_hearings_come_newest_first_without_a_composite_index(monkeypatch):
    docs = [{"id": "h1", "alert_id": "HL-4402", "created_at": "2026-10-18T01:00:00Z"},
            {"id": "h2", "alert_id": "HL-4429", "created_at": "2026-10-18T02:00:00Z"},
            {"id": "h3", "alert_id": "HL-4402", "created_at": "2026-10-18T03:00:00Z"}]
    monkeypatch.setattr(store, "_CLIENT", _Client(docs))
    assert [row["id"] for row in store.list_hearings("HL-4402")] == ["h3", "h1"]
    assert [row["id"] for row in store.list_hearings()] == ["h3", "h2", "h1"]
