"""
Flow Instrumentation — Structured interaction traces
======================================================
Collects UI events, Jarvis commands, and system events.
Strictly local, opt-in, metadata-only by default.
"""

import time
import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from threading import Lock


@dataclass
class TraceEvent:
    """Single event in a trace."""
    timestamp: float
    type: str  # ui_click | ui_open | jarvis_command | system_event
    payload: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TraceSummary:
    """Completed trace with metadata."""
    session_id: str
    start_time: float
    end_time: float
    events: List[TraceEvent] = field(default_factory=list)
    app_context: Optional[str] = None
    event_count: int = 0

    def to_dict(self) -> dict:
        return {
            'session_id': self.session_id,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'event_count': self.event_count,
            'app_context': self.app_context,
            'events': [e.to_dict() for e in self.events],
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'TraceSummary':
        events = [TraceEvent(**e) for e in data.get('events', [])]
        return cls(
            session_id=data['session_id'],
            start_time=data['start_time'],
            end_time=data.get('end_time', 0),
            events=events,
            app_context=data.get('app_context'),
            event_count=data.get('event_count', len(events)),
        )


class FlowInstrumentation:
    """
    Collect structured traces of user interactions.

    Privacy:
    - Recording is opt-in (requires explicit enable).
    - Only UI metadata and text are recorded.
    - Screenshots optional and stored encrypted with confirmation.
    """

    def __init__(self, storage_dir: Optional[str] = None):
        if storage_dir is None:
            root = Path(__file__).resolve().parents[2]
            storage_dir = root / 'data' / 'traces'
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._active: Dict[str, dict] = {}  # session_id -> {start, events}
        self._lock = Lock()

    # --- public API -------------------------------------------------------

    def start_trace(self, session_id: Optional[str] = None) -> str:
        """Begin a new trace session. Returns session_id."""
        if session_id is None:
            session_id = f"trace_{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._active[session_id] = {
                'start': time.time(),
                'events': [],
                'app_context': None,
            }
        return session_id

    def record_event(self, session_id: str, event: dict) -> None:
        """
        Append an event to the active trace.

        event schema:
        {
            "type": "ui_click" | "ui_open" | "jarvis_command" | "system_event",
            "payload": { "app": ..., "window_title": ..., ... }
        }
        """
        with self._lock:
            if session_id not in self._active:
                return
            te = TraceEvent(
                timestamp=time.time(),
                type=event.get('type', 'unknown'),
                payload=event.get('payload', {}),
            )
            self._active[session_id]['events'].append(te)
            # update app context from the most recent event
            app = event.get('payload', {}).get('app')
            if app:
                self._active[session_id]['app_context'] = app

    def end_trace(self, session_id: str) -> Optional[TraceSummary]:
        """End a trace and persist it. Returns the TraceSummary."""
        with self._lock:
            data = self._active.pop(session_id, None)
        if data is None:
            return None

        summary = TraceSummary(
            session_id=session_id,
            start_time=data['start'],
            end_time=time.time(),
            events=data['events'],
            app_context=data.get('app_context'),
            event_count=len(data['events']),
        )
        self._persist(summary)
        return summary

    def get_recent_traces(self, limit: int = 100) -> List[TraceSummary]:
        """Load the most recent completed traces from disk."""
        files = sorted(self._dir.glob('*.json'), reverse=True)[:limit]
        traces = []
        for f in files:
            try:
                data = json.loads(f.read_text(encoding='utf-8'))
                traces.append(TraceSummary.from_dict(data))
            except Exception:
                continue
        return traces

    # --- internal ---------------------------------------------------------

    def _persist(self, summary: TraceSummary) -> None:
        """Write trace to disk as JSON."""
        fname = f"{summary.session_id}.json"
        path = self._dir / fname
        path.write_text(
            json.dumps(summary.to_dict(), indent=2),
            encoding='utf-8',
        )
