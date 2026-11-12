import { afterEach, describe, expect, it, vi } from "vitest";
import { loadConfig } from "../config";
import { MockSafetyIndexClient, MockScenariosClient } from "../mocks/mockClients";
import { createDataClients } from "./index";
import { FastApiSafetyIndexClient, FastApiScenariosClient } from "./http/fastApiClients";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("loadConfig data sources", () => {
  it("uses the routing and safety APIs by default", () => {
    vi.stubEnv("VITE_DATA_SOURCE", "");
    vi.stubEnv("VITE_SAFETY_SOURCE", "");
    const config = loadConfig("");
    expect(config.dataSource).toBe("api");
    expect(config.safetySource).toBe("api");
  });

  it("lets the URL override each source independently", () => {
    const config = loadConfig("?source=api&safetySource=mock");
    expect(config.dataSource).toBe("api");
    expect(config.safetySource).toBe("mock");
  });

  it("reads the safety source from the environment", () => {
    vi.stubEnv("VITE_SAFETY_SOURCE", "mock");
    expect(loadConfig("").safetySource).toBe("mock");
  });

  it("falls back to the default for an invalid source", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const config = loadConfig("?source=remote&safetySource=remote");
    expect(config.dataSource).toBe("api");
    expect(config.safetySource).toBe("api");
    expect(warn).toHaveBeenCalledTimes(2);
  });
});

describe("createDataClients", () => {
  it("combines simulated trips with the safety API", () => {
    const clients = createDataClients(loadConfig("?source=mock&safetySource=api"));
    expect(clients.scenarios).toBeInstanceOf(MockScenariosClient);
    expect(clients.safety).toBeInstanceOf(FastApiSafetyIndexClient);
    expect(clients.tripsSimulated).toBe(true);
    expect(clients.safetySimulated).toBe(false);
  });

  it("uses only the APIs when both sources are api", () => {
    const clients = createDataClients(loadConfig("?source=api&safetySource=api"));
    expect(clients.scenarios).toBeInstanceOf(FastApiScenariosClient);
    expect(clients.safety).toBeInstanceOf(FastApiSafetyIndexClient);
    expect(clients.tripsSimulated).toBe(false);
    expect(clients.safetySimulated).toBe(false);
  });

  it("uses only mocks when both sources are mock", () => {
    const clients = createDataClients(loadConfig("?source=mock&safetySource=mock"));
    expect(clients.scenarios).toBeInstanceOf(MockScenariosClient);
    expect(clients.safety).toBeInstanceOf(MockSafetyIndexClient);
    expect(clients.tripsSimulated).toBe(true);
    expect(clients.safetySimulated).toBe(true);
  });
});
