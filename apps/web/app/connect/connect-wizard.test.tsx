import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConnectWizard } from "./connect-wizard";

const syntheticLeagueId = "99999999";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    className
  }: {
    readonly children: ReactNode;
    readonly href: string;
    readonly className?: string;
  }) => (
    <a className={className} href={href}>
      {children}
    </a>
  )
}));

vi.mock("@/lib/api-client", () => ({
  ApiClientError: class ApiClientError extends Error {
    constructor(
      message: string,
      readonly status: number
    ) {
      super(message);
      this.name = "ApiClientError";
    }
  },
  acceptAlphaInvite: vi.fn(async () => ({ status: "accepted" })),
  createLeague: vi.fn(async () => ({ leagueUuid: "11111111-1111-4111-8111-111111111111" })),
  validateCredentials: vi.fn(async () => undefined),
  storeCredentials: vi.fn(async () => ({ credentialVersion: 1 })),
  enqueueImportRun: vi.fn(async () => ({ runId: "22222222-2222-4222-8222-222222222222" }))
}));

describe("ConnectWizard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("clears ESPN secret fields when an import is queued", async () => {
    render(<ConnectWizard />);

    expect(screen.getByRole("button", { name: /Start import/ })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("ESPN league ID"), {
      target: { value: syntheticLeagueId }
    });
    fireEvent.change(screen.getByLabelText("SWID"), { target: { value: "{TEST-SWID}" } });
    fireEvent.change(screen.getByLabelText("espn_s2"), { target: { value: "test-token" } });
    fireEvent.click(screen.getByLabelText(/I confirm this is an unofficial/));
    expect(screen.getByRole("button", { name: /Start import/ })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: /Start import/ }));

    await waitFor(() => expect(screen.getByText(/Import queued/)).toBeInTheDocument());
    expect(screen.getByLabelText("SWID")).toHaveValue("");
    expect(screen.getByLabelText("espn_s2")).toHaveValue("");
  });

  it("renders credential validation errors on the connect surface", async () => {
    const { ApiClientError, validateCredentials } = await import("@/lib/api-client");
    vi.mocked(validateCredentials).mockRejectedValueOnce(
      new ApiClientError("credential failure", 401)
    );

    render(<ConnectWizard />);

    fireEvent.change(screen.getByLabelText("ESPN league ID"), {
      target: { value: syntheticLeagueId }
    });
    fireEvent.change(screen.getByLabelText("SWID"), { target: { value: "{TEST-SWID}" } });
    fireEvent.change(screen.getByLabelText("espn_s2"), { target: { value: "invalid-token" } });
    fireEvent.click(screen.getByLabelText(/I confirm this is an unofficial/));
    fireEvent.click(screen.getByRole("button", { name: /Start import/ }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Credential validation failed")
    );
    expect(screen.getByLabelText("SWID")).toHaveValue("");
    expect(screen.getByLabelText("espn_s2")).toHaveValue("");
  });

  it("clears ESPN secret fields when the API returns an unexpected failure", async () => {
    const { enqueueImportRun } = await import("@/lib/api-client");
    vi.mocked(enqueueImportRun).mockRejectedValueOnce(new Error("worker unavailable"));

    render(<ConnectWizard />);

    fireEvent.change(screen.getByLabelText("ESPN league ID"), {
      target: { value: syntheticLeagueId }
    });
    fireEvent.change(screen.getByLabelText("SWID"), { target: { value: "{TEST-SWID}" } });
    fireEvent.change(screen.getByLabelText("espn_s2"), { target: { value: "server-error" } });
    fireEvent.click(screen.getByLabelText(/I confirm this is an unofficial/));
    fireEvent.click(screen.getByRole("button", { name: /Start import/ }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Import could not be queued")
    );
    expect(screen.getByLabelText("SWID")).toHaveValue("");
    expect(screen.getByLabelText("espn_s2")).toHaveValue("");
  });
});
