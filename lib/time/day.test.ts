import { describe, it, expect } from "vitest";
import fixture from "@/fixtures/day-boundary.json";
import { localDateFor } from "./day";

describe("localDateFor", () => {
  for (const testCase of fixture.cases) {
    it(testCase.name, () => {
      const result = localDateFor(new Date(testCase.instant), testCase.timezone);
      expect(result).toBe(testCase.expectedLocalDate);
    });
  }
});
