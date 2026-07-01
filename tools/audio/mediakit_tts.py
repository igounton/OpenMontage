"""Mediakit TTS provider — Kokoro (free) and Chatterbox (voice cloning) via Modal-hosted API."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class MediakitTTS(BaseTool):
    name = "mediakit_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "mediakit"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:MEDIAKIT_BASE_URL", "env:MEDIAKIT_AUTH_TOKEN"]
    install_instructions = (
        "Set these in .env:\n"
        "  MEDIAKIT_BASE_URL=https://igounton--mediakit-web.modal.run\n"
        "  MEDIAKIT_AUTH_TOKEN=regie_..."
    )
    fallback = "openai_tts"
    fallback_tools = ["openai_tts", "elevenlabs_tts", "piper_tts"]
    agent_skills = ["text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
    ]
    supports = {
        "voice_cloning": True,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
    }
    best_for = [
        "free TTS narration",
        "zero-cost voice production",
        "quick explainer voiceovers",
    ]
    not_good_for = [
        "fully offline production",
        "extremely low-latency real-time speech",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "Text to convert to speech"},
            "voice": {
                "type": "string",
                "default": "af_nova",
                "description": "Kokoro voice name (default: af_nova, female). See /voices endpoint for full list.",
            },
            "speed": {
                "type": "number",
                "default": 1.0,
                "minimum": 0.5,
                "maximum": 2.0,
                "description": "Speech speed multiplier",
            },
            "engine": {
                "type": "string",
                "default": "kokoro",
                "enum": ["kokoro", "chatterbox"],
                "description": "TTS engine: kokoro (free, many voices) or chatterbox (voice cloning)",
            },
            "sample_audio_id": {
                "type": "string",
                "description": "Chatterbox only: file_id of a sample audio for voice cloning",
            },
            "exaggeration": {
                "type": "number",
                "default": 0.5,
                "minimum": 0,
                "maximum": 1,
                "description": "Chatterbox only: voice cloning exaggeration factor",
            },
            "output_path": {"type": "string", "description": "Path to write the audio file"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["text", "voice", "speed", "engine"]
    side_effects = ["writes audio file to output_path", "calls Mediakit API"]
    user_visible_verification = ["Listen to generated audio for natural speech quality"]

    DEFAULT_BASE_URL = "https://igounton--mediakit-web.modal.run"

    def get_status(self) -> ToolStatus:
        if os.environ.get("MEDIAKIT_BASE_URL") and os.environ.get("MEDIAKIT_AUTH_TOKEN"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # Mediakit runs on user's Modal account; no per-request cost

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        base_url = os.environ.get("MEDIAKIT_BASE_URL", self.DEFAULT_BASE_URL)
        auth_token = os.environ.get("MEDIAKIT_AUTH_TOKEN")
        if not auth_token:
            return ToolResult(
                success=False,
                error="MEDIAKIT_AUTH_TOKEN not set. " + self.install_instructions,
            )

        start = time.time()
        try:
            result = self._generate(inputs, base_url, auth_token)
        except Exception as exc:
            return ToolResult(success=False, error=f"Mediakit TTS failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        result.cost_usd = 0.0
        return result

    def _generate(
        self, inputs: dict[str, Any], base_url: str, auth_token: str
    ) -> ToolResult:
        import requests

        text = inputs["text"]
        engine = inputs.get("engine", "kokoro")
        output_path = Path(inputs.get("output_path", "tts_output.wav"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        headers = {"Authorization": auth_token}

        if engine == "kokoro":
            payload = {
                "text": text,
                "voice": inputs.get("voice", "af_nova"),
                "speed": inputs.get("speed", 1.0),
            }
            resp = requests.post(
                f"{base_url}/api/v1/media/audio-tools/tts/kokoro",
                headers=headers,
                data=payload,
                timeout=120,
            )
        else:
            payload = {
                "text": text,
                "exaggeration": inputs.get("exaggeration", 0.5),
            }
            sample_id = inputs.get("sample_audio_id")
            if sample_id:
                payload["sample_audio_id"] = sample_id

            resp = requests.post(
                f"{base_url}/api/v1/media/audio-tools/tts/chatterbox",
                headers=headers,
                data=payload,
                timeout=120,
            )

        resp.raise_for_status()
        file_id = resp.json().get("file_id")
        if not file_id:
            return ToolResult(
                success=False, error=f"No file_id in Mediakit response: {resp.text}"
            )

        # Poll for file readiness. Modal cold starts can take well over 10s, so
        # wait up to 90s and only download once status is "ready" — downloading
        # early 404s on the storage endpoint.
        import time as _time
        status_url = f"{base_url}/api/v1/media/storage/{file_id}/status"
        ready = False
        for attempt in range(90):
            status_resp = requests.get(status_url, headers=headers, timeout=30)
            if status_resp.ok and status_resp.json().get("status") == "ready":
                ready = True
                break
            _time.sleep(1)
        if not ready:
            return ToolResult(
                success=False,
                error=f"Mediakit file {file_id} not ready after 90s",
            )

        # Download the generated audio
        download_resp = requests.get(
            f"{base_url}/api/v1/media/storage/{file_id}",
            headers=headers,
            timeout=120,
        )
        download_resp.raise_for_status()

        output_path.write_bytes(download_resp.content)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "engine": engine,
                "voice": inputs.get("voice", "af_nova"),
                "file_id": file_id,
                "text_length": len(text),
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
            model=f"mediakit/{engine}",
        )
