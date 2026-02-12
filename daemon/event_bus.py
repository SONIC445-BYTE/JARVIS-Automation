from __future__ import annotations

from collections import defaultdict
from typing import Callable, DefaultDict, List


class EventBus:
    def __init__(self):
        self._subs: DefaultDict[str, List[Callable]] = defaultdict(list)

    def subscribe(self, event_name: str, callback: Callable) -> None:
        self._subs[event_name].append(callback)

    def publish(self, event_name: str, payload) -> None:
        for callback in self._subs.get(event_name, []):
            callback(payload)
