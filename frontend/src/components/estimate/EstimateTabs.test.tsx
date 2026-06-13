import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import EstimateTabs from "./EstimateTabs";

afterEach(cleanup);

describe("EstimateTabs", () => {
  it("shows active tab content and switches", async () => {
    render(
      <EstimateTabs
        smeta={<div>SMETA</div>}
        kp={<div>KP</div>}
        share={<div>SHARE</div>}
      />,
    );
    expect(screen.getByText("SMETA")).toBeInTheDocument();
    expect(screen.queryByText("KP")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "КП" }));
    expect(screen.getByText("KP")).toBeInTheDocument();
    expect(screen.queryByText("SMETA")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Поделиться" }));
    expect(screen.getByText("SHARE")).toBeInTheDocument();
  });
});
