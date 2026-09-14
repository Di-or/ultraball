import type {
  CardDetail,
  DeckImportError,
  DeckImportResponse,
  DeckValidateRequest,
  DeckValidateResponse,
  EnergyBasicsResponse,
  Matched,
  SearchRequest,
  SearchResponse,
} from "./types";

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

export async function validateDeck(
  request: DeckValidateRequest,
  signal?: AbortSignal
): Promise<DeckValidateResponse> {
  const response = await fetch("/decks/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });
  if (!response.ok) {
    throw new Error(`deck validation failed: ${response.status} ${await response.text()}`);
  }
  return (await response.json()) as DeckValidateResponse;
}

export class DeckImportRejected extends Error {
  lines: string[];

  constructor(detail: DeckImportError) {
    super(detail.message);
    this.lines = detail.lines;
  }
}

export async function importDeck(text: string): Promise<DeckImportResponse> {
  const response = await fetch("/decks/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (response.status === 422) {
    const body = (await response.json()) as { detail: DeckImportError };
    throw new DeckImportRejected(body.detail);
  }
  if (!response.ok) {
    throw new Error(`deck import failed: ${response.status} ${await response.text()}`);
  }
  return (await response.json()) as DeckImportResponse;
}

export async function getEnergyBasics(): Promise<EnergyBasicsResponse> {
  const response = await fetch("/energy/basics");
  if (!response.ok) {
    throw new Error(`energy basics failed: ${response.status} ${await response.text()}`);
  }
  return (await response.json()) as EnergyBasicsResponse;
}
