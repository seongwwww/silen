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
              // - differenceRepository.ts: 차이 확인 경계가 세션 client와 조립하는 팩토리.
              //   경계(합성 루트)가 client→repository를 엮어 서비스에 주입한다.
              //   도메인 질의 자체는 여전히 서비스를 거친다.
              // - diaryRepository.ts: 일기 보기 경계가 세션 client와 조립하는 팩토리.
              //   /review와 구조가 같은 RLS 스코프 읽기 전용 화면이다.
              // 주간 리포트까지 6개가 되어 기준을 다시 검토했다. 합성 루트의
              // repository 팩토리 import는 필요하지만 wildcard는 저장소가 아닌
              // 구현까지 새어 나갈 수 있어, 좁은 exact allowlist를 유지한다.
              // 다음 읽기 화면은 서비스 facade 도입을 먼저 검토할 것.
              except: [
                "./supabase.ts",
                "./memoryRepository.ts",
                "./differenceRepository.ts",
                "./diaryRepository.ts",
                "./userRepository.ts",
                "./weeklyRepository.ts",
              ],
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
    // worker·evals는 파이썬이다. 1차 JS/TS가 없고, .venv·캐시까지 훑다가
    // 권한이 깨진 디렉터리를 만나면 lint 전체가 EPERM으로 죽는다.
    // (.gitignore를 따르게 하는 방식은 worker/src·tests가 추적 파일이라 안 통한다.)
    "worker/**",
    "evals/**",
    // supabase start가 만드는 런타임 생성물. 컨테이너용 번들이 들어 있어
    // 스택을 띄운 개발자에게서만 lint가 깨진다(.gitignore 대상이지만
    // eslint는 .gitignore를 보지 않는다).
    "supabase/.temp/**",
    "supabase/.branches/**",
  ]),
]);

export default eslintConfig;
