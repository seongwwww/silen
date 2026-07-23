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
              // 예외는 "경계가 조립하는 인프라"에 한한다:
              // - supabase.ts: SSR 클라이언트 생성(요청·쿠키에 묶여 서비스에 못 넣음)
              // - memoryRepository.ts: 클라이언트를 서비스 포트로 감싸는 팩토리.
              //   경계(합성 루트)가 client→repository를 엮어 서비스에 주입한다.
              //   도메인 질의 자체는 여전히 서비스를 거친다.
              except: ["./supabase.ts", "./memoryRepository.ts"],
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
