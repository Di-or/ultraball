import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type { SearchResponse } from "./lib/types";

function jsonResponse(body: SearchResponse): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("submits the NL query, ticks the returned filters on, and a later chip edit sends no query", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        results: [],
        total: 0,
        limit: 30,
        offset: 0,
        filters: { format: "standard" },
      })
    );

    render(<App />);
    await waitFor(() => expect(screen.queryByText("Searching…")).not.toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Search query"), {
      target: { value: "energy acceleration under 130 HP" },
    });
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        results: [],
        total: 0,
        limit: 30,
        offset: 0,
        filters: { format: "standard", hp: { lte: 130 } },
      })
    );
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => expect(screen.getByLabelText("Maximum HP")).toHaveValue("130"));

    const parseCall = fetchMock.mock.calls.find(
      (call) => JSON.parse(call[1]?.body as string).query === "energy acceleration under 130 HP"
    );
    expect(parseCall).toBeDefined();

    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        results: [],
        total: 0,
        limit: 30,
        offset: 0,
        filters: { format: "standard", hp: { lte: 130 }, category: "Pokemon" },
      })
    );
    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "Pokemon" } });

    await waitFor(() => {
      const lastCall = fetchMock.mock.calls.at(-1);
      const body = JSON.parse(lastCall?.[1]?.body as string);
      expect(body.query).toBeNull();
      expect(body.filters.category).toBe("Pokemon");
    });
  });

  it("shows a removable concept indicator after an NL query, which drops the query on removal", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ results: [], total: 0, limit: 30, offset: 0, filters: { format: "standard" } })
    );

    render(<App />);
    await waitFor(() => expect(screen.queryByText("Searching…")).not.toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Search query"), { target: { value: "acceleration" } });
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ results: [], total: 0, limit: 30, offset: 0, filters: { format: "standard" } })
    );
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => expect(screen.getByText("acceleration")).toBeInTheDocument());
    expect(screen.getByRole("status")).toHaveTextContent("Concept:acceleration");

    fetchMock.mockResolvedValueOnce(
      jsonResponse({ results: [], total: 0, limit: 30, offset: 0, filters: { format: "standard" } })
    );
    fireEvent.click(screen.getByRole("button", { name: "Remove concept" }));

    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
    const lastBody = JSON.parse(fetchMock.mock.calls.at(-1)?.[1]?.body as string);
    expect(lastBody.query).toBeNull();
  });

  it("opens a card-detail modal from a result and closes it", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        results: [
          {
            entity_id: "charizard",
            printing_id: "swsh4-1",
            name: "Charizard",
            category: "Pokemon",
            hp: 170,
            types: ["Fire"],
            stage: "Stage 2",
            sub_category: [],
            regulation_mark: "F",
            rarity: "Rare Holo",
            set_id: "swsh4",
            is_standard_legal: true,
            matched: null,
          },
        ],
        total: 1,
        limit: 30,
        offset: 0,
        filters: { format: "standard" },
      })
    );

    render(<App />);
    await waitFor(() => expect(screen.getByText("Charizard")).toBeInTheDocument());

    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          entity_id: "charizard",
          printing_id: "swsh4-1",
          name: "Charizard",
          category: "Pokemon",
          hp: 170,
          types: ["Fire"],
          stage: "Stage 2",
          evolve_from: "Charmeleon",
          retreat: 3,
          regulation_mark: "F",
          rarity: "Rare Holo",
          set_id: "swsh4",
          sub_category: [],
          trainer_type: null,
          energy_type: null,
          attacks: [],
          abilities: [],
          attack_costs: [4],
          image: null,
          is_standard_legal: true,
          tags: [],
          printings: [],
          matched: null,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );
    fireEvent.click(screen.getByRole("button", { name: /Charizard/ }));

    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
