import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import ErrorBoundary from "./ErrorBoundary";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function ThrowingChild(): never {
  throw new Error("test crash");
}

describe("ErrorBoundary", () => {
  it("renders fallback UI when a child throws", () => {
    // Suppress the expected console.error from React + the boundary itself
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>
    );

    expect(screen.getByText("Что-то пошло не так. Обновите страницу.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Обновить" })).toBeInTheDocument();

    consoleSpy.mockRestore();
  });

  it("renders children normally when no error is thrown", () => {
    render(
      <ErrorBoundary>
        <div>Контент</div>
      </ErrorBoundary>
    );
    expect(screen.getByText("Контент")).toBeInTheDocument();
    expect(screen.queryByText("Что-то пошло не так. Обновите страницу.")).not.toBeInTheDocument();
  });
});
