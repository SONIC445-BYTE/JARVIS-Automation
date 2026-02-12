from __future__ import annotations

from typing import Any, Callable


class STTIntegration:
    """
    Adapter to bridge existing STT streams into the automation daemon.
    This does not replace STT implementation; it only subscribes to transcripts.
    """

    def __init__(self, daemon):
        self.daemon = daemon

    def subscribe(self, stt_source: Any) -> None:
        """
        Supported STT source patterns:
        - stt_source.subscribe(callback)
        - stt_source.register_listener(callback)
        - stt_source.on_result callback attr
        """
        callback: Callable[[str], None] = self.forward_transcript
        if hasattr(stt_source, "subscribe"):
            stt_source.subscribe(callback)
            return
        if hasattr(stt_source, "register_listener"):
            stt_source.register_listener(callback)
            return
        if hasattr(stt_source, "on_result"):
            stt_source.on_result = callback
            return
        raise TypeError("Unsupported STT source interface")

    def forward_transcript(self, text: str) -> None:
        self.daemon.receive_transcript(text)


def wire_to_existing_stt(stt_source: Any, daemon) -> STTIntegration:
    integration = STTIntegration(daemon=daemon)
    integration.subscribe(stt_source)
    return integration
