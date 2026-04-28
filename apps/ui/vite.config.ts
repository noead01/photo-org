import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { configDefaults } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/testing/setupTests.ts",
    exclude: [...configDefaults.exclude, "tests/e2e/**"]
  }
});
