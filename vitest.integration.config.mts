import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: { tsconfigPaths: true },
  test: {
    environment: "node",
    // 통합 테스트만. 로컬 Supabase 스택이 떠 있어야 한다.
    include: ["**/*.integration.test.ts"],
    exclude: ["**/node_modules/**", "**/.next/**"],
    // 컨테이너 기동 직후에는 첫 연결이 느릴 수 있다.
    testTimeout: 30_000,
  },
});
