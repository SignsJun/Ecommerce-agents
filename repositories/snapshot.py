from domain.business.snapshot import BusinessStateSnapshot


class InMemorySnapshotRepository:
    def __init__(self) -> None:
        self._items: dict[str, BusinessStateSnapshot] = {}
        self._order: list[str] = []

    def save(self, snapshot: BusinessStateSnapshot) -> None:
        if snapshot.snapshot_id not in self._items:
            self._order.append(snapshot.snapshot_id)
        self._items[snapshot.snapshot_id] = snapshot

    def get(self, snapshot_id: str) -> BusinessStateSnapshot | None:
        return self._items.get(snapshot_id)

    def latest(self) -> BusinessStateSnapshot | None:
        if not self._order:
            return None
        return self._items[self._order[-1]]

    def current_version(self) -> int:
        latest = self.latest()
        return 0 if latest is None else latest.version
