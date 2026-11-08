import { fileURLToPath } from "node:url";
import { configDefaults, defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    // The `@/*` alias tsconfig.json declares ("@/*": ["./*"]).
    alias: { "@": fileURLToPath(new URL("./", import.meta.url)) },
  },
  test: {
    // Plain-logic unit tests only; screens and components are covered by the acceptance checks.
    include: ["**/*.test.ts"],
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
});
