import { describe, it, expect } from "vitest";
import { assertValidTransition, InvalidTransitionError } from "./difference";

describe("assertValidTransition", () => {
  it("candidate → confirmed/dismissed 허용", () => {
    expect(() => assertValidTransition("candidate", "confirmed")).not.toThrow();
    expect(() => assertValidTransition("candidate", "dismissed")).not.toThrow();
  });
  it("confirmed/dismissed → candidate(undo) 허용", () => {
    expect(() => assertValidTransition("confirmed", "candidate")).not.toThrow();
    expect(() => assertValidTransition("dismissed", "candidate")).not.toThrow();
  });
  it("confirmed → dismissed 직접 전이 거부", () => {
    expect(() => assertValidTransition("confirmed", "dismissed")).toThrow(InvalidTransitionError);
  });
  it("동일 상태 전이 거부", () => {
    expect(() => assertValidTransition("candidate", "candidate")).toThrow(InvalidTransitionError);
  });
});
