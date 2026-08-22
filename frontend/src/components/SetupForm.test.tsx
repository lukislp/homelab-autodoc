import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SetupForm } from "./SetupForm";

describe("SetupForm", () => {
  it("hides the issuer URL field for the github provider by default", () => {
    render(<SetupForm onSubmit={vi.fn()} submitting={false} error={null} />);

    expect(screen.queryByLabelText(/issuer url/i)).not.toBeInTheDocument();
  });

  it("shows the issuer URL field when oidc is selected", async () => {
    const user = userEvent.setup();
    render(<SetupForm onSubmit={vi.fn()} submitting={false} error={null} />);

    await user.selectOptions(screen.getByLabelText(/provider/i), "oidc");

    expect(screen.getByLabelText(/issuer url/i)).toBeInTheDocument();
  });

  it("submits the github form with the entered values", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<SetupForm onSubmit={onSubmit} submitting={false} error={null} />);

    await user.type(screen.getByLabelText(/client id/i), "abc");
    await user.type(screen.getByLabelText(/client secret/i), "s3cret");
    await user.type(screen.getByLabelText(/allowed identity/i), "lukislp");
    await user.click(screen.getByRole("button", { name: /save and continue/i }));

    expect(onSubmit).toHaveBeenCalledWith({
      provider: "github",
      client_id: "abc",
      client_secret: "s3cret",
      allowed_identity: "lukislp",
      issuer_url: undefined,
    });
  });

  it("submits the issuer_url when oidc is selected", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<SetupForm onSubmit={onSubmit} submitting={false} error={null} />);

    await user.selectOptions(screen.getByLabelText(/provider/i), "oidc");
    await user.type(screen.getByLabelText(/issuer url/i), "https://auth.example.com");
    await user.type(screen.getByLabelText(/client id/i), "abc");
    await user.type(screen.getByLabelText(/client secret/i), "s3cret");
    await user.type(screen.getByLabelText(/allowed identity/i), "me@example.com");
    await user.click(screen.getByRole("button", { name: /save and continue/i }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ provider: "oidc", issuer_url: "https://auth.example.com" }),
    );
  });

  it("shows the error message when given one", () => {
    render(<SetupForm onSubmit={vi.fn()} submitting={false} error="something went wrong" />);

    expect(screen.getByText("something went wrong")).toBeInTheDocument();
  });

  it("disables the submit button while submitting", () => {
    render(<SetupForm onSubmit={vi.fn()} submitting={true} error={null} />);

    expect(screen.getByRole("button")).toBeDisabled();
  });
});
