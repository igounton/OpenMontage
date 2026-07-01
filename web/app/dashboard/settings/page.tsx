"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const SERVER = process.env.NEXT_PUBLIC_SERVER_URL ?? "http://localhost:8000";

type HealthData = { status: string; service: string };
type SystemInfo = { serverOk: boolean; jobs: number; brands: number };
type Seam = { active: string; available: string[]; planned: string[] };
type Backends = { storage: Seam; queue: Seam; auth: Seam };

const SEAM_LABELS: Record<keyof Backends, { title: string; desc: string }> = {
  queue: { title: "Task Queue", desc: "Scheduling layer that drives pipeline execution" },
  storage: { title: "Object Storage", desc: "Storage and delivery of artifacts / assets / final renders" },
  auth: { title: "Authentication", desc: "Access control method" },
};

export default function SettingsPage() {
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [backends, setBackends] = useState<Backends | null>(null);

  useEffect(() => {
    async function load() {
      const [health, jobs, brands, caps] = await Promise.allSettled([
        fetch(`${SERVER}/health`).then((r) => r.json() as Promise<HealthData>),
        fetch(`${SERVER}/jobs`).then((r) => r.json()),
        fetch(`${SERVER}/brands`).then((r) => r.json()),
        fetch(`${SERVER}/system/capabilities`).then((r) => r.json()),
      ]);
      setInfo({
        serverOk: health.status === "fulfilled" && health.value.status === "ok",
        jobs: jobs.status === "fulfilled" ? (jobs.value.jobs?.length ?? 0) : 0,
        brands: brands.status === "fulfilled" ? (brands.value.brand_kits?.length ?? 0) : 0,
      });
      if (caps.status === "fulfilled" && caps.value?.backends) {
        setBackends(caps.value.backends as Backends);
      }
    }
    load();
  }, []);

  const env = {
    "LLM Model": "anthropic/claude-sonnet-4.6",
    "Video Generation": "MaaS · LTX-2.3 / Seedance (CNY billing)",
    "Image Generation": "MaaS · Flux2",
    "Speech Synthesis": "MaaS · qwen3-tts-flash / IndexTTS",
    "Cost Tracking": "cost_tracker source ledger (cost_log.json)",
  };

  return (
    <div className="p-8 max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground text-sm mt-1">System status and evolution roadmap</p>
      </div>

      {/* System status */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">System Status</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm">AI Production Server</span>
            {info === null ? (
              <span className="text-xs text-muted-foreground">Checking…</span>
            ) : (
              <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${info.serverOk ? "bg-green-500/15 text-green-400 border-green-500/30" : "bg-red-500/15 text-red-400 border-red-500/30"}`}>
                {info.serverOk ? "● Online" : "● Offline"}
              </span>
            )}
          </div>
          {info && (
            <>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Total Projects</span>
                <span className="font-mono">{info.jobs}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Brand Kits</span>
                <span className="font-mono">{info.brands}</span>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Stack */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Current Tech Stack</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2.5">
            {Object.entries(env).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">{k}</span>
                <span className="text-foreground font-mono text-xs">{v}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Evolution seams — live from /system/capabilities (M5-3) */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Evolution Seams (M5-3)</CardTitle>
        </CardHeader>
        <CardContent>
          {backends === null ? (
            <p className="text-xs text-muted-foreground">Loading backend capabilities…</p>
          ) : (
            <div className="space-y-4">
              {(Object.keys(SEAM_LABELS) as (keyof Backends)[]).map((key) => {
                const seam = backends[key];
                const meta = SEAM_LABELS[key];
                return (
                  <div key={key} className="flex items-start gap-3">
                    <span className="mt-1 w-2 h-2 rounded-full shrink-0 bg-green-400" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium">{meta.title}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded border font-medium bg-green-500/15 text-green-400 border-green-500/30">
                          Running: {seam.active}
                        </span>
                        {seam.planned.map((p) => (
                          <span key={p} className="text-[10px] px-1.5 py-0.5 rounded border font-medium bg-muted text-muted-foreground border-border">
                            {p} · Planned
                          </span>
                        ))}
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {meta.desc} — interface reserved (server/app/interfaces); swapping implementations requires no caller changes.
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
