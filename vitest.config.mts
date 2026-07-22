import { defineConfig } from "vitest/config";

export default defineConfig({
  // Vite가 tsconfig의 paths(@/*)를 네이티브로 해석한다.
  // vite-tsconfig-paths 플러그인은 더 이상 필요하지 않다.
  resolve: { tsconfigPaths: true },
  test: {
    // 순수 모듈 단위 테스트. 컴포넌트 테스트를 추가할 때 jsdom과
    // @vitejs/plugin-react·@testing-library/react를 함께 도입한다.
    environment: "node",
    include: ["lib/**/*.test.ts", "app/**/*.test.ts"],
    // 통합 테스트는 별도 러너로 분리한다(vitest.integration.config.mts).
    // 이 제외가 없으면 lib/**/*.test.ts 패턴이 *.integration.test.ts 도 잡는다.
    exclude: ["**/node_modules/**", "**/.next/**", "**/*.integration.test.ts"],
  },
});
