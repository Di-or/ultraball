import type { CardDetail, Matched, SearchRequest, SearchResponse } from "./types";

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

export async function getCardDetail(
  entityId: string,
  matched?: Matched | null,
  signal?: AbortSignal
): Promise<CardDetail> {
  const params = new URLSearchParams();
  for (const tag of matched?.tags ?? []) params.append("matched_tags", tag);
  if (matched?.semantic) params.set("matched_semantic", "true");

  const query = params.toString();
  const response = await fetch(`/cards/${encodeURIComponent(entityId)}${query ? `?${query}` : ""}`, {
    signal,
  });
  if (!response.ok) {
    throw new Error(`card detail failed: ${response.status} ${await response.text()}`);
  }
  return (await response.json()) as CardDetail;
}
