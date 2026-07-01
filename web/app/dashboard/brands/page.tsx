"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type BrandKit = {
  kit_id: string;
  brand_name: string;
  slogan: string;
  industry: string;
  tone_keywords: string[];
  color_palette: string[];
  target_audience: string;
  logo_url: string;
  style_notes: string;
  updated_at: number;
};

const SERVER = process.env.NEXT_PUBLIC_SERVER_URL ?? "http://localhost:8000";

export default function BrandsPage() {
  const [kits, setKits] = useState<BrandKit[]>([]);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<BrandKit | null>(null);
  const [form, setForm] = useState(emptyForm());
  const [saving, setSaving] = useState(false);

  function emptyForm() {
    return {
      brand_name: "", slogan: "", industry: "",
      tone_keywords: "", color_palette: "", target_audience: "",
      logo_url: "", style_notes: "",
    };
  }

  async function load() {
    const res = await fetch(`${SERVER}/brands`);
    if (res.ok) setKits((await res.json()).brand_kits ?? []);
  }

  // Async fetch: setState happens after await, not synchronously in the effect.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load(); }, []);

  function startCreate() {
    setForm(emptyForm());
    setEditing(null);
    setCreating(true);
  }

  function startEdit(kit: BrandKit) {
    setForm({
      brand_name: kit.brand_name,
      slogan: kit.slogan,
      industry: kit.industry,
      tone_keywords: kit.tone_keywords.join(", "),
      color_palette: kit.color_palette.join(", "),
      target_audience: kit.target_audience,
      logo_url: kit.logo_url,
      style_notes: kit.style_notes,
    });
    setEditing(kit);
    setCreating(true);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    const payload = {
      ...form,
      tone_keywords: form.tone_keywords.split(",").map((s) => s.trim()).filter(Boolean),
      color_palette: form.color_palette.split(",").map((s) => s.trim()).filter(Boolean),
    };
    if (editing) {
      await fetch(`${SERVER}/brands/${editing.kit_id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } else {
      await fetch(`${SERVER}/brands`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    }
    await load();
    setCreating(false);
    setEditing(null);
    setSaving(false);
  }

  async function handleDelete(kit_id: string) {
    if (!confirm("Delete this brand kit?")) return;
    await fetch(`${SERVER}/brands/${kit_id}`, { method: "DELETE" });
    await load();
  }

  return (
    <div className="p-8 max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Brand Library</h1>
          <p className="text-muted-foreground text-sm mt-1">Save your brand assets so AI can automatically reference them and generate style-consistent videos</p>
        </div>
        {!creating && (
          <Button onClick={startCreate}>+ New Brand Kit</Button>
        )}
      </div>

      {/* Create / Edit form */}
      {creating && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{editing ? "Edit Brand Kit" : "New Brand Kit"}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSave} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium block mb-1.5">Brand Name *</label>
                  <Input required value={form.brand_name} onChange={(e) => setForm(f => ({ ...f, brand_name: e.target.value }))} placeholder="Puppy Coffee Maker" />
                </div>
                <div>
                  <label className="text-sm font-medium block mb-1.5">Industry</label>
                  <Input value={form.industry} onChange={(e) => setForm(f => ({ ...f, industry: e.target.value }))} placeholder="Consumer electronics / FMCG / Tech…" />
                </div>
              </div>
              <div>
                <label className="text-sm font-medium block mb-1.5">Slogan</label>
                <Input value={form.slogan} onChange={(e) => setForm(f => ({ ...f, slogan: e.target.value }))} placeholder="Great coffee, not just for cafés" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium block mb-1.5">Tone Keywords (comma-separated)</label>
                  <Input value={form.tone_keywords} onChange={(e) => setForm(f => ({ ...f, tone_keywords: e.target.value }))} placeholder="Warm, ritual, quality" />
                </div>
                <div>
                  <label className="text-sm font-medium block mb-1.5">Brand Colors (Hex, comma-separated)</label>
                  <Input value={form.color_palette} onChange={(e) => setForm(f => ({ ...f, color_palette: e.target.value }))} placeholder="#1A1A1A, #C8A96E, #F5F0E8" />
                </div>
              </div>
              <div>
                <label className="text-sm font-medium block mb-1.5">Target Audience</label>
                <Input value={form.target_audience} onChange={(e) => setForm(f => ({ ...f, target_audience: e.target.value }))} placeholder="Urban professionals aged 25-40 who value quality of life" />
              </div>
              <div>
                <label className="text-sm font-medium block mb-1.5">Style Notes</label>
                <Textarea rows={2} value={form.style_notes} onChange={(e) => setForm(f => ({ ...f, style_notes: e.target.value }))} placeholder="Slow motion, warm tones, macro close-ups, no voiceover…" />
              </div>
              <div className="flex gap-3 pt-2">
                <Button type="submit" disabled={saving}>{saving ? "Saving…" : "Save"}</Button>
                <Button type="button" variant="outline" onClick={() => { setCreating(false); setEditing(null); }}>Cancel</Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Kit list */}
      {kits.length === 0 && !creating && (
        <div className="flex flex-col items-center justify-center h-48 border border-dashed border-border rounded-lg gap-3">
          <p className="text-muted-foreground text-sm">No brand kits yet</p>
          <Button variant="outline" onClick={startCreate}>Create your first one</Button>
        </div>
      )}

      <div className="space-y-3">
        {kits.map((kit) => (
          <Card key={kit.kit_id} className="hover:border-foreground/20 transition-colors">
            <CardContent className="pt-4 pb-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-semibold text-sm">{kit.brand_name}</h3>
                    {kit.industry && (
                      <span className="text-xs text-muted-foreground border border-border rounded px-1.5 py-0.5">{kit.industry}</span>
                    )}
                  </div>
                  {kit.slogan && (
                    <p className="text-xs text-muted-foreground mt-0.5 italic">&ldquo;{kit.slogan}&rdquo;</p>
                  )}
                  <div className="flex gap-3 mt-2 flex-wrap">
                    {kit.tone_keywords.slice(0, 4).map((k) => (
                      <span key={k} className="text-xs bg-muted px-2 py-0.5 rounded-full">{k}</span>
                    ))}
                    {kit.color_palette.slice(0, 4).map((c) => (
                      <span
                        key={c}
                        className="w-4 h-4 rounded-full border border-border inline-block"
                        style={{ backgroundColor: c }}
                        title={c}
                      />
                    ))}
                  </div>
                  {kit.target_audience && (
                    <p className="text-xs text-muted-foreground mt-1.5">Audience: {kit.target_audience}</p>
                  )}
                </div>
                <div className="flex gap-2 shrink-0">
                  <Button size="sm" variant="outline" onClick={() => startEdit(kit)}>Edit</Button>
                  <Button size="sm" variant="outline" className="text-destructive border-destructive/40 hover:bg-destructive/10" onClick={() => handleDelete(kit.kit_id)}>Delete</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
