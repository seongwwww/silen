import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,

  // backend.md 2자산 3계층 — 의존 방향을 기계 검사한다.
  // 문서로만 두면 지켜지지 않으므로 lint가 막는다.
  {
    files: ["app/**/*.{ts,tsx}"],
    rules: {
      "import/no-restricted-paths": [
        "error",
        {
          zones: [
            {
              target: "./app",
              from: "./lib/repositories",
              // supabase.ts는 도메인 저장소가 아니라 클라이언트 생성 인프라다.
              // Supabase SSR 클라이언트는 요청·쿠키(프레임워크 타입)에 묶여
              // 있어 프레임워크를 모르는 서비스 계층에 넣을 수 없다. 이 하나만
              // 경계가 직접 만진다. 도메인 데이터 접근은 여전히 서비스를 거친다.
              except: ["./supabase.ts"],
              message:
                "계층 건너뛰기 금지(backend.md): 경계에서 저장소를 직접 호출하지 말고 서비스를 거친다.",
            },
          ],
        },
      ],
    },
  },
  {
    files: ["lib/services/**/*.ts"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["next", "next/*"],
              message:
                "역방향 의존 금지(backend.md): 서비스 계층은 Request/Response를 알면 안 된다.",
            },
          ],
        },
      ],
    },
  },

  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
