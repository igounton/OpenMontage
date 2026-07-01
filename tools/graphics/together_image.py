"""Together AI image generation (FLUX models via Together's OpenAI-compatible API).

Together AI hosts Black Forest Labs FLUX models and others behind a single
images endpoint. This tool mirrors flux_image.py but talks to Together.
"""

from __future__ import annotations

import base64
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


class TogetherImage(BaseTool):
    name = "together_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "together"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.API

    dependencies = ["env:TOGETHER_API_KEY"]
    install_instructions = (
        "Set TOGETHER_API_KEY to your Together AI API key.\n"
        "  Get one at https://api.together.ai/settings/api-keys"
    )
    agent_skills = ["flux-best-practices"]

    capabilities = ["generate_image", "generate_illustration", "text_to_image"]
    supports = {
        "negative_prompt": True,
        "seed": True,
        "custom_size": True,
    }
    best_for = [
        "stylized conceptual / metaphor visuals (explainers, brand)",
        "fast cheap FLUX generation via Together (~$0.002 schnell, ~$0.035 dev)",
        "vertical / custom aspect ratios up to ~1 megapixel",
    ]
    not_good_for = ["text rendering inside images", "offline generation"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "negative_prompt": {"type": "string", "default": ""},
            "width": {"type": "integer", "default": 1024},
            "height": {"type": "integer", "default": 1024},
            "model": {
                "type": "string",
                "enum": [
                    "black-forest-labs/FLUX.1-schnell",
                    "black-forest-labs/FLUX.1-dev",
                    "black-forest-labs/FLUX.1-pro",
                    "black-forest-labs/FLUX.1-Kontext-dev",
                    "stabilityai/stable-diffusion-xl-base-1.0",
                ],
                "default": "black-forest-labs/FLUX.1-schnell",
            },
            "steps": {"type": "integer"},
            "seed": {"type": "integer"},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout", "5xx"])
    idempotency_key_fields = ["prompt", "width", "height", "seed", "model"]
    side_effects = ["writes image file to output_path", "calls Together AI API"]
    user_visible_verification = ["Inspect generated image for relevance and quality"]

    def _get_api_key(self) -> str | None:
        return os.environ.get("TOGETHER_API_KEY")

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._get_api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        model = inputs.get("model", "black-forest-labs/FLUX.1-schnell")
        if "pro" in model:
            return 0.05
        if "dev" in model:
            return 0.035
        return 0.002  # schnell

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="No Together AI API key found. " + self.install_instructions,
            )

        import requests

        start = time.time()
        model = inputs.get("model", "black-forest-labs/FLUX.1-schnell")
        prompt = inputs["prompt"]
        width = inputs.get("width", 1024)
        height = inputs.get("height", 1024)

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "mode": "url",
            "width": width,
            "height": height,
        }
        if inputs.get("seed") is not None:
            payload["seed"] = inputs["seed"]
        if inputs.get("steps"):
            payload["steps"] = inputs["steps"]
        if inputs.get("negative_prompt"):
            payload["negative_prompt"] = inputs["negative_prompt"]

        url = "https://api.together.xyz/v1/images/generations"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        data: dict[str, Any] | None = None
        last_err = ""
        for attempt in range(self.retry_policy.max_retries + 1):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=120)
            except Exception as e:  # network blip
                last_err = f"request failed: {e}"
                time.sleep(1.0 * (attempt + 1))
                continue
            if response.status_code == 200:
                data = response.json()
                break
            # Retryable: rate limit (429) or server error (5xx)
            if response.status_code in (429, *range(500, 600)) and attempt < self.retry_policy.max_retries:
                last_err = f"HTTP {response.status_code}: {response.text[:300]}"
                time.sleep(1.5 * (2 ** attempt))  # ~1.5s, 3s backoff
                continue
            return ToolResult(
                success=False,
                error=(
                    f"Together image generation failed: HTTP {response.status_code}: "
                    f"{response.text[:500]}. NOTE: FLUX on Together caps near ~1 megapixel; "
                    f"for vertical use 768x1344 or 832x1216 (not 1024x1792)."
                ),
            )
        if data is None:
            return ToolResult(success=False, error=f"Together image generation failed after retries: {last_err}")

        try:

            items = data.get("data") or data.get("images") or []
            if not items:
                return ToolResult(success=False, error=f"Together returned no image data: {data}")

            item = items[0]
            output_path = Path(inputs.get("output_path", "generated_image.png"))
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if item.get("url"):
                img = requests.get(item["url"], timeout=60)
                img.raise_for_status()
                output_path.write_bytes(img.content)
            elif item.get("b64_json"):
                output_path.write_bytes(base64.b64decode(item["b64_json"]))
            else:
                return ToolResult(success=False, error=f"Together returned no url/b64: {item}")

        except Exception as e:
            return ToolResult(success=False, error=f"Together image generation failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": "together",
                "model": model,
                "prompt": prompt,
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            seed=inputs.get("seed"),
            model=model,
        )
