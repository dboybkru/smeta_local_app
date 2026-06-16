import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import PriceLevelsPage from "./PriceLevelsPage";

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}

// /auth/me returns 401 — AuthProvider sets user=null; page still renders fine
const ME_401 = () => jsonResponse({ detail: "Unauthorized" }, 401);

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("PriceLevelsPage", () => {
  it("lists existing levels", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (String(url).includes("/auth/me")) return ME_401();
      if (String(url).includes("/auth/refresh")) return jsonResponse({}, 401);
      return jsonResponse([{ id: 1, name: "Розница", sort_order: 0 }]);
    }));
    render(<MemoryRouter><AuthProvider><PriceLevelsPage /></AuthProvider></MemoryRouter>);
    expect(await screen.findByText("Розница")).toBeInTheDocument();
  });

  it("creates a new level and reloads", async () => {
    let priceLevelCalls = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (String(url).includes("/auth/me")) return ME_401();
      if (String(url).includes("/auth/refresh")) return jsonResponse({}, 401);
      // price-levels endpoint
      if ((init?.method ?? "GET") === "POST") {
        return jsonResponse({ id: 2, name: "Опт", sort_order: 1 }, 201);
      }
      priceLevelCalls++;
      if (priceLevelCalls === 1) return jsonResponse([]); // initial load
      return jsonResponse([{ id: 2, name: "Опт", sort_order: 1 }]); // reload
    }));
    render(<MemoryRouter><AuthProvider><PriceLevelsPage /></AuthProvider></MemoryRouter>);
    await screen.findByText("Новый уровень");
    await userEvent.type(screen.getByPlaceholderText("Название уровня"), "Опт");
    await userEvent.click(screen.getByText("Добавить"));
    expect(await screen.findByText("Опт")).toBeInTheDocument();
  });

  it("shows the 409 error when a level is in use", async () => {
    let priceLevelCalls = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      if (String(url).includes("/auth/me")) return ME_401();
      if (String(url).includes("/auth/refresh")) return jsonResponse({}, 401);
      if ((init?.method ?? "GET") === "DELETE") {
        return jsonResponse({ detail: "Уровень используется в ценах — удалить нельзя" }, 409);
      }
      priceLevelCalls++;
      if (priceLevelCalls === 1) return jsonResponse([{ id: 1, name: "Розница", sort_order: 0 }]);
      return jsonResponse([]);
    }));
    render(<MemoryRouter><AuthProvider><PriceLevelsPage /></AuthProvider></MemoryRouter>);
    await screen.findByText("Розница");
    await userEvent.click(screen.getByText("Удалить"));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("используется в ценах")
    );
  });
});
