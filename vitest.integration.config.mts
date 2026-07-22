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
    // 통합 테스트는 하나의 로컬 DB를 공유하고 beforeEach가 전역으로
    // 사용자를 지운다. 파일을 병렬 실행하면 한 파일의 정리가 다른
    // 파일이 방금 만든 사용자를 지워 서로 간섭한다. 반드시 직렬로 돈다.
    fileParallelism: false,
  },
});
