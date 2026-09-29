import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import type { SearchResponse } from "./lib/types";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

// App now shares its global `fetch` with the deck panel (energy tray + debounced legality)
// and the card-detail modal, so the stub routes by URL instead of a single response queue.
function stubFetch(searchResponses: SearchResponse[], options: { cardDetail?: unknown } = {}) {
  const queue = [...searchResponses];
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    void init;
    const url = typeof input === "string" ? input : input.toString();
    if (url === "/search") {
      const body = queue.shift();
      return Promise.resolve(jsonResponse(body ?? { results: [], total: 0, limit: 30, offset: 0, filters: {} }));
    }
    if (url.startsWith("/cards/")) {
      return Promise.resolve(jsonResponse(options.cardDetail ?? {}));
    }
    if (url === "/sets") {
      return Promise.resolve(
        jsonResponse([
          { id: "sv1", code: "SVI", release_date: "2023-03-31" },
          { id: "swsh1", code: "SSH", release_date: "2020-02-07" },
        ])
      );
    }
    if (url === "/energy/basics") {
      return Promise.resolve(jsonResponse({ palette: [] }));
    }
    if (url === "/decks/validate") {
      return Promise.resolve(
        jsonResponse({ legal: true, counts: { pokemon: 0, trainer: 0, energy: 0, total: 0 }, violations: [] })
      );
    }
    return Promise.reject(new Error(`unexpected fetch to ${url}`));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("App", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("submits the NL query, ticks the returned filters on, and a later chip edit sends no query", async () => {
    const fetchMock = stubFetch([
      { results: [], total: 0, limit: 30, offset: 0, filters: { format: "standard" } },
      { results: [], total: 0, limit: 30, offset: 0, filters: { format: "standard", hp: { lte: 130 } } },
      { results: [], total: 0, limit: 30, offset: 0, filters: { format: "standard", hp: { lte: 130 }, category: "Pokemon" } },
    ]);

    render(<App />);
    await waitFor(() => expect(screen.queryByText("Searching…")).not.toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Search query"), {
      target: { value: "energy acceleration under 130 HP" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => expect(screen.getByLabelText("Maximum HP")).toHaveValue("130"));

    const parseCall = fetchMock.mock.calls.find(
      (call) => call[0] === "/search" && JSON.parse(call[1]?.body as string).query === "energy acceleration under 130 HP"
    );
    expect(parseCall).toBeDefined();

    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "Pokemon" } });

    await waitFor(() => {
      const lastSearchCall = fetchMock.mock.calls.filter((call) => call[0] === "/search").at(-1);
      const body = JSON.parse(lastSearchCall?.[1]?.body as string);
      expect(body.query).toBeNull();
      expect(body.filters.category).toBe("Pokemon");
    });
  });

  it("loads the sets into the dropdown and sends the chosen set id with the search", async () => {
    const fetchMock = stubFetch([]);

    render(<App />);
    await waitFor(() => expect(screen.getByRole("option", { name: "SSH" })).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Set"), { target: { value: "swsh1" } });

    await waitFor(() => {
      const lastSearchCall = fetchMock.mock.calls.filter((call) => call[0] === "/search").at(-1);
      const body = JSON.parse(lastSearchCall?.[1]?.body as string);
      expect(body.filters.set_id).toBe("swsh1");
    });
  });

  it("shows a removable concept indicator after an NL query, which drops the query on removal", async () => {
    const fetchMock = stubFetch([
      { results: [], total: 0, limit: 30, offset: 0, filters: { format: "standard" } },
      { results: [], total: 0, limit: 30, offset: 0, filters: { format: "standard" } },
      { results: [], total: 0, limit: 30, offset: 0, filters: { format: "standard" } },
    ]);

    render(<App />);
    await waitFor(() => expect(screen.queryByText("Searching…")).not.toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Search query"), { target: { value: "acceleration" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => expect(screen.getByText("acceleration")).toBeInTheDocument());
    expect(screen.getByRole("status")).toHaveTextContent("Concept:acceleration");

    fireEvent.click(screen.getByRole("button", { name: "Remove concept" }));

    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
    const lastSearchCall = fetchMock.mock.calls.filter((call) => call[0] === "/search").at(-1);
    const lastBody = JSON.parse(lastSearchCall?.[1]?.body as string);
    expect(lastBody.query).toBeNull();
  });

  it("keeps the conceptually-ranked response after resolving, without a second fetch that would downgrade it to plain filtering", async () => {
    const fetchMock = stubFetch([
      { results: [], total: 0, limit: 30, offset: 0, filters: { format: "standard" } },
      {
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
            set_code: "swsh4",
            local_id: "1",
            is_standard_legal: true,
            matched: { tags: ["acceleration"], semantic: true },
          },
        ],
        total: 1,
        limit: 30,
        offset: 0,
        filters: { format: "standard" },
      },
    ]);

    render(<App />);
    await waitFor(() => expect(screen.queryByText("Searching…")).not.toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Search query"), { target: { value: "acceleration" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => expect(screen.getByText("acceleration")).toBeInTheDocument());
    // The conceptual match chip from the parse-driven response must still be on screen — a
    // second, `query: null` fetch would have overwritten it with an unranked, unmatched one.
    expect(screen.getByText("meaning")).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter((call) => call[0] === "/search")).toHaveLength(2);
  });

  it("opens a card-detail modal from a result and closes it", async () => {
    stubFetch(
      [
        {
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
              set_code: "swsh4",
              local_id: "1",
              is_standard_legal: true,
              matched: null,
            },
          ],
          total: 1,
          limit: 30,
          offset: 0,
          filters: { format: "standard" },
        },
      ],
      {
        cardDetail: {
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
        },
      }
    );

    render(<App />);
    await waitFor(() => expect(screen.getByText("Charizard")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /Charizard/ }));

    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
