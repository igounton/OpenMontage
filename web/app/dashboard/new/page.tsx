"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  CONTENT_TYPES, isPipelineAvailable, computeMorePipelines, toPipelineOption,
  type PipelineInfo, type PipelineOption,
} from "@/lib/pipeline-picker";

const SERVER = process.env.NEXT_PUBLIC_SERVER_URL ?? "http://localhost:8000";

type BrandKit = { kit_id: string; brand_name: string; slogan: string };
type Step = "type" | "wizard";

export default function NewProjectPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("type");
  const [selectedType, setSelectedType] = useState<PipelineOption | null>(null);
  const [brandKits, setBrandKits] = useState<BrandKit[]>([]);
  const [pipelines, setPipelines] = useState<PipelineInfo[]>([]);
  const [form, setForm] = useState({
    projectName: "",
    brandName: "",
    slogan: "",
    duration: "30",
    notes: "",
    brandKitId: "",
    budgetUsd: "",
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch(`${SERVER}/brands`)
      .then((r) => r.json())
      .then((d) => setBrandKits(d.brand_kits ?? []))
      .catch(() => {});
    fetch(`${SERVER}/pipelines`)
      .then((r) => r.json())
      .then((d) => setPipelines(d.pipelines ?? []))
      .catch(() => {});
  }, []);

  const availableNames = new Set(pipelines.map((p) => p.name));
  const morePipelines = computeMorePipelines(pipelines);

  function applyKit(kit: BrandKit) {
    setForm((f) => ({
      ...f,
      brandKitId: kit.kit_id,
      brandName: kit.brand_name,
      slogan: kit.slogan,
    }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedType) return;
    setLoading(true);

    const res = await fetch(`${SERVER}/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_name: form.projectName || form.brandName.replace(/\s+/g, "-"),
        content_type: selectedType.id,
        pipeline: selectedType.pipeline,
        brand_info: {
          brand_name: form.brandName,
          slogan: form.slogan,
          notes: form.notes,
        },
        options: {
          duration_seconds: parseInt(form.duration),
          // Provider/model is chosen at runtime by the capability selectors
          // (image_selector / video_selector / tts_selector) from whatever is
          // credentialed in the registry — no hardcoded model id needed.
          ...(form.brandKitId ? { brand_kit_id: form.brandKitId } : {}),
          ...(form.budgetUsd && Number(form.budgetUsd) > 0
            ? { budget_usd: Number(form.budgetUsd) }
            : {}),
        },
      }),
    });

    const data = await res.json();
    if (res.ok && data.job_id) {
      router.push(`/dashboard/jobs/${data.job_id}`);
    } else {
      alert("Creation failed: " + JSON.stringify(data));
      setLoading(false);
    }
  }

  if (step === "type") {
    return (
      <div className="p-8 max-w-3xl">
        <h1 className="text-2xl font-bold tracking-tight mb-2">Choose a video type</h1>
        <p className="text-muted-foreground text-sm mb-8">Pick the type of video you want to make — AI will automatically select the best production pipeline.</p>
        <div className="grid grid-cols-1 gap-3">
          {CONTENT_TYPES.map((ct) => {
            // Available once the engine reports the mapped pipeline (or before
            // /pipelines has loaded, so the UI isn't empty on first paint).
            const available = isPipelineAvailable(availableNames, ct.pipeline);
            return (
              <button
                key={ct.id}
                disabled={!available}
                onClick={() => { setSelectedType(ct); setStep("wizard"); }}
                className={`text-left p-4 rounded-lg border transition-colors ${
                  available
                    ? "border-border hover:border-foreground/40 hover:bg-accent cursor-pointer"
                    : "border-border/40 opacity-40 cursor-not-allowed"
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{ct.label}</span>
                      {!available && <Badge variant="outline" className="text-xs">Not enabled</Badge>}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">{ct.description}</p>
                  </div>
                  {available && <span className="text-muted-foreground text-lg">→</span>}
                </div>
              </button>
            );
          })}
        </div>

        {morePipelines.length > 0 && (
          <div className="mt-8">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
              More engine pipelines
            </h2>
            <div className="grid grid-cols-1 gap-3">
              {morePipelines.map((p) => (
                <button
                  key={p.name}
                  onClick={() => {
                    setSelectedType(toPipelineOption(p));
                    setStep("wizard");
                  }}
                  className="text-left p-4 rounded-lg border border-border hover:border-foreground/40 hover:bg-accent cursor-pointer transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-medium text-sm font-mono">{p.name}</span>
                        {p.stability && p.stability !== "production" && (
                          <Badge variant="outline" className="text-xs">{p.stability}</Badge>
                        )}
                        <span className="text-xs text-muted-foreground">{p.stages.length} stages</span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{p.description}</p>
                    </div>
                    <span className="text-muted-foreground text-lg">→</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="p-8 max-w-xl">
      <button
        onClick={() => setStep("type")}
        className="text-sm text-muted-foreground hover:text-foreground mb-6 flex items-center gap-1"
      >
        ← Choose a different type
      </button>

      <h1 className="text-2xl font-bold tracking-tight mb-1">{selectedType?.label}</h1>
      <p className="text-muted-foreground text-sm mb-8">{selectedType?.description}</p>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Brand Kit selector */}
        {brandKits.length > 0 && (
          <div className="space-y-2">
            <h2 className="text-sm font-semibold text-foreground/70 uppercase tracking-wider">Quick-apply a Brand Kit</h2>
            <div className="flex gap-2 flex-wrap">
              {brandKits.map((kit) => (
                <button
                  key={kit.kit_id}
                  type="button"
                  onClick={() => applyKit(kit)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                    form.brandKitId === kit.kit_id
                      ? "bg-foreground text-background border-foreground"
                      : "border-border hover:border-foreground/40"
                  }`}
                >
                  {kit.brand_name}
                </button>
              ))}
              {form.brandKitId && (
                <button
                  type="button"
                  onClick={() => setForm(f => ({ ...f, brandKitId: "" }))}
                  className="text-xs px-3 py-1.5 text-muted-foreground hover:text-foreground"
                >
                  × Clear
                </button>
              )}
            </div>
          </div>
        )}

        {brandKits.length > 0 && <Separator />}

        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-foreground/70 uppercase tracking-wider">Brand info</h2>
          <div className="space-y-3">
            <div>
              <label className="text-sm font-medium block mb-1.5">Brand / product name *</label>
              <Input
                required
                placeholder="e.g. Puppy Coffee Maker"
                value={form.brandName}
                onChange={(e) => setForm(f => ({ ...f, brandName: e.target.value }))}
              />
            </div>
            <div>
              <label className="text-sm font-medium block mb-1.5">Project name (optional)</label>
              <Input
                placeholder="Leave blank to auto-generate"
                value={form.projectName}
                onChange={(e) => setForm(f => ({ ...f, projectName: e.target.value }))}
              />
            </div>
            <div>
              <label className="text-sm font-medium block mb-1.5">Brand slogan (optional)</label>
              <Input
                placeholder="e.g. Great coffee, not just for cafés"
                value={form.slogan}
                onChange={(e) => setForm(f => ({ ...f, slogan: e.target.value }))}
              />
            </div>
          </div>
        </div>

        <Separator />

        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-foreground/70 uppercase tracking-wider">Video settings</h2>
          <div className="space-y-3">
            <div>
              <label className="text-sm font-medium block mb-1.5">Duration</label>
              <div className="flex gap-2">
                {["15", "30", "60"].map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => setForm(f => ({ ...f, duration: d }))}
                    className={`px-4 py-1.5 rounded-md text-sm border transition-colors ${
                      form.duration === d
                        ? "bg-foreground text-background border-foreground"
                        : "border-border hover:border-foreground/40"
                    }`}
                  >
                    {d}s
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-sm font-medium block mb-1.5">Budget cap $ (optional)</label>
              <Input
                type="number"
                min="0"
                step="0.5"
                placeholder="e.g. 50 — pause for confirmation once cumulative cost exceeds this"
                value={form.budgetUsd}
                onChange={(e) => setForm(f => ({ ...f, budgetUsd: e.target.value }))}
              />
              <p className="text-xs text-muted-foreground mt-1">
                Costs are in USD. Leave blank for no budget gate.
              </p>
            </div>
            <div>
              <label className="text-sm font-medium block mb-1.5">Additional notes (optional)</label>
              <Textarea
                placeholder="Target audience, emotional tone, reference style, etc..."
                rows={3}
                value={form.notes}
                onChange={(e) => setForm(f => ({ ...f, notes: e.target.value }))}
              />
            </div>
          </div>
        </div>

        <Button type="submit" className="w-full" disabled={loading || !form.brandName}>
          {loading ? "Submitting..." : "Start AI production →"}
        </Button>
      </form>
    </div>
  );
}
