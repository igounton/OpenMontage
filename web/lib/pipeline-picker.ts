// Pure logic for the new-job pipeline picker, extracted so it's testable
// without the fetch-driven page shell (mirrors components/job-status.tsx).

export type PipelineInfo = {
  name: string;
  description: string;
  category?: string;
  stability?: string;
  stages: string[];
};

export type PipelineOption = {
  id: string;
  label: string;
  description: string;
  pipeline: string;
  stability?: string;
};

// Friendly Chinese entry points mapped to engine pipelines.
export const CONTENT_TYPES: PipelineOption[] = [
  { id: "marketing_film", label: "Marketing film", description: "Brand story · Product launch · 15-60s emotional short", pipeline: "cinematic" },
  { id: "explainer",      label: "Explainer video",   description: "Motion graphics · Feature demo · Tutorial",              pipeline: "animated-explainer" },
  { id: "podcast",        label: "Podcast clips",   description: "Long audio → short video highlights",                pipeline: "podcast-repurpose" },
  { id: "demo",           label: "Product demo",   description: "Screen recording + AI voiceover",                 pipeline: "screen-demo" },
  { id: "short",          label: "Bulk shorts", description: "Long video → multiple vertical shorts",                  pipeline: "clip-factory" },
];

/**
 * A curated card is enabled once the engine reports its mapped pipeline.
 * Before /pipelines has loaded (availableNames is empty), everything is
 * enabled so the UI isn't all-disabled on first paint.
 */
export function isPipelineAvailable(availableNames: Set<string>, pipeline: string): boolean {
  return availableNames.size === 0 || availableNames.has(pipeline);
}

/** Engine pipelines with no curated Chinese card — offered directly. */
export function computeMorePipelines(
  pipelines: PipelineInfo[],
  contentTypes: PipelineOption[] = CONTENT_TYPES
): PipelineInfo[] {
  const featured = new Set(contentTypes.map((c) => c.pipeline));
  return pipelines.filter((p) => !featured.has(p.name));
}

/** Build the PipelineOption the picker needs from a raw /pipelines entry. */
export function toPipelineOption(p: PipelineInfo): PipelineOption {
  return {
    id: p.name,
    label: p.name,
    description: p.description,
    pipeline: p.name,
    stability: p.stability,
  };
}
