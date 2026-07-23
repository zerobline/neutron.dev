import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [react(), tsconfigPaths()],
  test: {
    environment: "jsdom",
    pool: "forks",
    testTimeout: 10_000,
    setupFiles: ["./tests/setup/vitest.setup.ts"],
    globals: true,
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.d.ts"],
      thresholds: {
        // Statements/branches leave a little room for defensive optional-chains
        // in streaming/websocket and phase-card presentation helpers.
        statements: 99.5,
        branches: 98,
        functions: 100,
        lines: 100,
      },
    },
  },
});
