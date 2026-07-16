import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // ponytail: e2e/ is Playwright's; keep it out of the vitest run.
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
