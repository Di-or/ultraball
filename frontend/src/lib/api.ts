import type { SearchRequest, SearchResponse } from "./types";

export async function search(request: SearchRequest, signal?: AbortSignal): Promise<SearchResponse> {
  const response = await fetch("/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });
  if (!response.ok) {
    throw new Error(`search failed: ${response.status} ${await response.text()}`);
  }
  return (await response.json()) as SearchResponse;
}
