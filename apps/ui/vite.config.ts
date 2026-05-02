import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { configDefaults } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/testing/setupTests.ts",
    exclude: [...configDefaults.exclude, "tests/e2e/**"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/main.tsx",
        "src/pages/BrowseRoutePage.tsx",
        "src/pages/browseFocusState.ts",
        "src/testing/**"
      ],
      thresholds: {
        statements: 80,
        lines: 80
      }
    }
  }
});
