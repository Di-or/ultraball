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
});
