import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: { tsconfigPaths: true },
  test: {
    environment: "node",
    globals: true,
    include: ["lib/**/*.test.ts", "app/**/*.test.{ts,tsx}", "components/**/*.test.tsx"],
    exclude: ["**/node_modules/**", "**/.next/**", "**/*.integration.test.*"],
  },
});
