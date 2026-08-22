import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, getJson, post, postJson } from "./client";

function mockFetchOnce(response: Partial<Response> & { json?: () => Promise<unknown> }) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({}),
    ...response,
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("api/client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("getJson sends credentials and returns the parsed body", async () => {
    const fetchMock = mockFetchOnce({ json: async () => ({ hello: "world" }) });

    const result = await getJson<{ hello: string }>("/api/thing");

    expect(result).toEqual({ hello: "world" });
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/thing");
    expect(init.credentials).toBe("include");
  });

  it("postJson sends the body as JSON with a POST method", async () => {
    const fetchMock = mockFetchOnce({ json: async () => ({ status: "ok" }) });

    await postJson("/api/setup", { provider: "github" });

    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ provider: "github" }));
  });

  it("post sends no body", async () => {
    const fetchMock = mockFetchOnce({ json: async () => ({ status: "ok" }) });

    await post("/api/admin/devices/ABCD-1234/approve");

    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.body).toBeUndefined();
  });

  it("throws an ApiError with the server-provided detail on a non-2xx response", async () => {
    mockFetchOnce({ ok: false, status: 401, json: async () => ({ detail: "not logged in" }) });

    await expect(getJson("/api/admin/devices")).rejects.toMatchObject(
      new ApiError(401, "not logged in"),
    );
  });

  it("falls back to statusText when the error body isn't JSON", async () => {
    mockFetchOnce({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: async () => {
        throw new Error("not json");
      },
    });

    await expect(getJson("/api/thing")).rejects.toMatchObject(
      new ApiError(500, "Internal Server Error"),
    );
  });

  it("returns undefined for a 204 response without parsing a body", async () => {
    mockFetchOnce({
      status: 204,
      json: () => {
        throw new Error("should not be called");
      },
    });

    const result = await getJson("/api/thing");

    expect(result).toBeUndefined();
  });
});
