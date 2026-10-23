export interface PresetSummary {
  id: string;
  label: string;
  description: string;
}

export const API_BASE = "/api";

function isPreset(value: unknown): value is PresetSummary {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return typeof v.id === "string" && typeof v.label === "string" && typeof v.description === "string";
}

// Returns null on ANY failure (backend down, bad response). The app treats null as
// "no live backend" and falls back to the recorded replay instead of showing a broken screen.
export async function fetchPresets(baseUrl: string = API_BASE): Promise<PresetSummary[] | null> {
  try {
    const response = await fetch(`${baseUrl}/presets`);
    if (!response.ok) return null;
    const data: unknown = await response.json();
    return Array.isArray(data) ? data.filter(isPreset) : null;
  } catch {
    return null;
  }
}
