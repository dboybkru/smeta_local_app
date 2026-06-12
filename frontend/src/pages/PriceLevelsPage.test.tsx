import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import PriceLevelsPage from "./PriceLevelsPage";

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("PriceLevelsPage", () => {
  it("lists existing levels", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse([{ id: 1, name: "Розница", sort_order: 0 }])));
    render(<MemoryRouter><AuthProvider><PriceLevelsPage /></AuthProvider></MemoryRouter>);
    expect(await screen.findByText("Розница")).toBeInTheDocument();
  });

  it("creates a new level and reloads", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([])) // initial load
      .mockResolvedValueOnce(jsonResponse({ id: 2, name: "Опт", sort_order: 1 }, 201)) // create
      .mockResolvedValueOnce(jsonResponse([{ id: 2, name: "Опт", sort_order: 1 }])); // reload
    vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter><AuthProvider><PriceLevelsPage /></AuthProvider></MemoryRouter>);
    await screen.findByText("Новый уровень");
    await userEvent.type(screen.getByPlaceholderText("Название уровня"), "Опт");
    await userEvent.click(screen.getByText("Добавить"));
    expect(await screen.findByText("Опт")).toBeInTheDocument();
  });

  it("shows the 409 error when a level is in use", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse([{ id: 1, name: "Розница", sort_order: 0 }]))
      .mockResolvedValueOnce(jsonResponse({ detail: "Уровень используется в ценах — удалить нельзя" }, 409));
    vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter><AuthProvider><PriceLevelsPage /></AuthProvider></MemoryRouter>);
    await screen.findByText("Розница");
    await userEvent.click(screen.getByText("Удалить"));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("используется в ценах")
    );
  });
});
