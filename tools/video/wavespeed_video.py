"""WaveSpeed AI video generation via the *direct* WaveSpeed platform API.

Talks straight to WaveSpeed's prediction API (submit → poll → download). Model is
selected as a URL path segment, not a body field.

Auth/config (read from environment / .env):
  - WAVESPEED_API_KEY       : WaveSpeed platform API key (required)
  - WAVESPEED_API_BASE_URL  : API base. Default https://api.wavespeed.ai/api/v3
  - WAVESPEED_VIDEO_MODEL   : default text-to-video model path segment
  - WAVESPEED_I2V_MODEL     : default image-to-video model path segment

Flow (async):
  POST {base}/{model}                       -> task id (id | task_id | prediction_id)
  GET  {base}/predictions/{task_id}/result  -> status + output url(s)
  download mp4 to output_path
"""

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

DEFAULT_BASE = "https://api.wavespeed.ai/api/v3"
DEFAULT_T2V_MODEL = "bytedance/seedance-2.0/text-to-video"
DEFAULT_I2V_MODEL = "bytedance/seedance-2.0/image-to-video"

# status buckets returned by the /result poll endpoint
_DONE = {"completed", "complete", "succeeded", "success", "finished"}
_FAILED = {"failed", "error", "cancelled", "canceled"}
# anything else (pending/queued/running/processing/starting/submitted) → keep polling

# body keys we forward verbatim when present (everything else stays out of the payload)
_PASSTHROUGH = (
    "negative_prompt", "seed", "duration", "fps",
    "aspect_ratio", "resolution", "width", "height",
)


class WaveSpeedVideo(BaseTool):
    name = "wavespeed_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "wavespeed"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set WAVESPEED_API_KEY to your WaveSpeed API key (get one at https://wavespeed.ai).\n"
        "  Optional: WAVESPEED_API_BASE_URL (default https://api.wavespeed.ai/api/v3),\n"
        "  WAVESPEED_VIDEO_MODEL / WAVESPEED_I2V_MODEL to change default models."
    )
    agent_skills = ["ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
    }
    best_for = [
        "text-to-video and image-to-video via WaveSpeed (Seedance / Kling)",
        "direct WaveSpeed access without a fal.ai account",
    ]
    not_good_for = ["offline generation", "guaranteed-deterministic output"]
    fallback_tools = ["minimax_video_direct", "kling_video", "veo_video", "wan_video"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "Text prompt for the video."},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video"],
                "default": "text_to_video",
            },
            "model": {
                "type": "string",
                "description": "WaveSpeed model path segment, e.g. bytedance/seedance-2.0/text-to-video. "
                               "Defaults per operation from WAVESPEED_VIDEO_MODEL / WAVESPEED_I2V_MODEL.",
            },
            "first_frame_image": {
                "type": "string",
                "description": "For image_to_video: a public image URL or a local image path (sent as base64 data URI).",
            },
            "duration": {"type": "integer", "description": "Clip length in seconds (model-dependent)."},
            "aspect_ratio": {"type": "string", "description": "e.g. 16:9, 9:16, 1:1 (model-dependent)."},
            "resolution": {"type": "string", "description": "e.g. 480p, 720p, 1080p (model-dependent)."},
            "negative_prompt": {"type": "string"},
            "seed": {"type": "integer"},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "operation", "duration", "resolution", "seed"]
    side_effects = ["writes video file to output_path", "calls WaveSpeed API (costs money)"]
    user_visible_verification = ["Watch generated clip for motion coherence and prompt adherence"]

    # ---- config helpers ----
    def _api_key(self) -> str | None:
        return os.environ.get("WAVESPEED_API_KEY")

    def _base_url(self) -> str:
        return (os.environ.get("WAVESPEED_API_BASE_URL") or DEFAULT_BASE).rstrip("/")

    def _default_model(self, operation: str) -> str:
        if operation == "image_to_video":
            return os.environ.get("WAVESPEED_I2V_MODEL") or DEFAULT_I2V_MODEL
        return os.environ.get("WAVESPEED_VIDEO_MODEL") or DEFAULT_T2V_MODEL

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Rough placeholder; WaveSpeed prices per model/resolution/duration.
        dur = int(inputs.get("duration", 5) or 5)
        return round(0.10 * max(1, dur), 2)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 180.0

    # ---- helpers ----
    @staticmethod
    def _image_payload(value: str) -> str:
        """Accept a URL/data-URI as-is; turn a local path into a base64 data URI."""
        if value.startswith(("http://", "https://", "data:")):
            return value
        p = Path(value)
        if not p.exists():
            raise FileNotFoundError(f"first_frame_image not found: {value}")
        import base64
        mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{b64}"

    @staticmethod
    def _extract_task_id(payload: dict) -> str | None:
        for src in (payload, payload.get("data") or {}):
            if isinstance(src, dict):
                for k in ("id", "task_id", "prediction_id"):
                    if src.get(k):
                        return str(src[k])
        return None

    @staticmethod
    def _extract_output_url(obj: Any) -> str | None:
        """Recursively find the first output/download URL in a poll result."""
        if isinstance(obj, str):
            return obj if obj.startswith("http") else None
        if isinstance(obj, list):
            for item in obj:
                url = WaveSpeedVideo._extract_output_url(item)
                if url:
                    return url
            return None
        if isinstance(obj, dict):
            for k in ("url", "uri", "download_url"):
                v = obj.get(k)
                if isinstance(v, str) and v.startswith("http"):
                    return v
            for k in ("output", "outputs", "result", "results", "video", "videos"):
                if k in obj:
                    url = WaveSpeedVideo._extract_output_url(obj[k])
                    if url:
                        return url
        return None

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._api_key()
        if not api_key:
            return ToolResult(success=False, error="WAVESPEED_API_KEY not set. " + self.install_instructions)

        import requests

        start = time.time()
        base = self._base_url()
        operation = inputs.get("operation", "text_to_video")
        model = inputs.get("model") or self._default_model(operation)
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        payload: dict[str, Any] = {"prompt": inputs["prompt"]}
        for k in _PASSTHROUGH:
            if inputs.get(k) is not None:
                payload[k] = inputs[k]
        if operation == "image_to_video":
            img = inputs.get("first_frame_image")
            if not img:
                return ToolResult(success=False, error="image_to_video requires 'first_frame_image'.")
            try:
                payload["image"] = self._image_payload(img)
            except Exception as e:
                return ToolResult(success=False, error=str(e))

        try:
            # 1) Submit generation task — model is a path segment
            submit = requests.post(
                f"{base}/{model.lstrip('/')}", headers=headers, json=payload, timeout=60
            )
            submit.raise_for_status()
            task_id = self._extract_task_id(submit.json())
            if not task_id:
                return ToolResult(success=False, error=f"WaveSpeed returned no task id: {submit.text[:300]}")

            # 2) Poll until done
            download_url = None
            deadline = time.time() + 900  # 15 min hard cap
            while time.time() < deadline:
                time.sleep(5)
                q = requests.get(
                    f"{base}/predictions/{task_id}/result", headers=headers, timeout=30
                )
                q.raise_for_status()
                qd = q.json()
                data = qd.get("data") if isinstance(qd.get("data"), dict) else qd
                status = str(data.get("status") or data.get("state") or "").lower()
                if status in _DONE:
                    download_url = self._extract_output_url(qd)
                    break
                if status in _FAILED:
                    return ToolResult(success=False, error=f"WaveSpeed generation failed: {str(qd)[:300]}")
                # else keep polling
            if not download_url:
                return ToolResult(success=False, error=f"WaveSpeed task {task_id} timed out or returned no output URL.")

            # 3) Download mp4
            vid = requests.get(download_url, timeout=300)
            vid.raise_for_status()
            suffix = Path(download_url.split("?")[0]).suffix or ".mp4"
            output_path = Path(inputs.get("output_path", f"wavespeed_output{suffix}"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(vid.content)

        except requests.HTTPError as e:
            return ToolResult(success=False, error=f"WaveSpeed HTTP error: {e} :: {getattr(e.response, 'text', '')[:300]}")
        except Exception as e:
            return ToolResult(success=False, error=f"WaveSpeed video generation failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": "wavespeed",
                "platform": base,
                "model": model,
                "operation": operation,
                "task_id": task_id,
                "prompt": inputs["prompt"],
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
