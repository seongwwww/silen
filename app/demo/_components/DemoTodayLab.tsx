"use client";

import { useState } from "react";
import { TodayScreen } from "@/app/_components/TodayScreen";
import {
  DEMO_LABELS,
  DEMO_VIEWS,
  type DemoState,
} from "../fixtures";

export function DemoTodayLab({
  initialState = "quiet",
}: {
  initialState?: DemoState;
}) {
  const [state, setState] = useState<DemoState>(initialState);

  return (
    <div>
      <div className="sticky top-0 z-40 border-b bg-background/95 px-4 py-3 backdrop-blur">
        <div className="mx-auto max-w-md">
          <p className="text-xs font-semibold tracking-wide text-muted-foreground">
            FRONTEND MOCK DATA
          </p>
          <label htmlFor="demo-state" className="mt-2 block text-sm font-medium">
            테스트 상태
          </label>
          <select
            id="demo-state"
            value={state}
            onChange={(event) => setState(event.target.value as DemoState)}
            className="mt-1 min-h-11 w-full rounded-xl border bg-card px-3"
          >
            {(Object.keys(DEMO_LABELS) as DemoState[]).map((key) => (
              <option key={key} value={key}>
                {DEMO_LABELS[key]}
              </option>
            ))}
          </select>
          <p className="mt-2 text-xs text-muted-foreground">
            실제 사용자 데이터나 서버 요청을 사용하지 않는 화면 테스트용입니다.
          </p>
        </div>
      </div>
      <TodayScreen
        key={state}
        view={DEMO_VIEWS[state]}
        requestDiary={async () => {}}
        decideDifference={async () => true}
      />
    </div>
  );
}
