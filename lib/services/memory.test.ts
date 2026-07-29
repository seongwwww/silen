import { describe, it, expect, vi } from "vitest";
import {
  createMemory,
  EmptyMemoryError,
  ForeignAssetPathError,
  type MemoryRepository,
  assertNotFuture,
  FutureOccurrenceError,
} from "./memory";

function stubRepo(overrides: Partial<MemoryRepository> = {}): MemoryRepository {
  return {
    insertMemory: vi.fn().mockResolvedValue({ id: "mem-1" }),
    insertEmotion: vi.fn().mockResolvedValue(undefined),
    insertAsset: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

const USER = "11111111-1111-1111-1111-111111111111";

describe("createMemory", () => {
  it("텍스트만으로 메모를 만든다", async () => {
    const repo = stubRepo();
    const result = await createMemory(repo, { userId: USER, text: "오늘 그 노래 또 들음" });

    expect(repo.insertMemory).toHaveBeenCalledWith({
      userId: USER,
      rawText: "오늘 그 노래 또 들음",
      occurredAt: null,
    });
    expect(repo.insertEmotion).not.toHaveBeenCalled();
    expect(repo.insertAsset).not.toHaveBeenCalled();
    expect(result).toEqual({ memoryId: "mem-1" });
  });

  it("감정 칩을 valence로 매핑한다", async () => {
    const repo = stubRepo();
    await createMemory(repo, { userId: USER, text: "좋았다", emotion: "good" });
    expect(repo.insertEmotion).toHaveBeenCalledWith({ memoryId: "mem-1", valence: 1 });

    const repo2 = stubRepo();
    await createMemory(repo2, { userId: USER, text: "별로", emotion: "bad" });
    expect(repo2.insertEmotion).toHaveBeenCalledWith({ memoryId: "mem-1", valence: -1 });

    const repo3 = stubRepo();
    await createMemory(repo3, { userId: USER, text: "그냥", emotion: "neutral" });
    expect(repo3.insertEmotion).toHaveBeenCalledWith({ memoryId: "mem-1", valence: 0 });
  });

  it("사진 경로를 asset으로 기록하고 mime을 유추한다", async () => {
    const repo = stubRepo();
    await createMemory(repo, { userId: USER, assetPaths: [`${USER}/a.jpg`, `${USER}/b.png`] });

    expect(repo.insertAsset).toHaveBeenCalledWith({
      memoryId: "mem-1",
      fileUrl: `${USER}/a.jpg`,
      mimeType: "image/jpeg",
    });
    expect(repo.insertAsset).toHaveBeenCalledWith({
      memoryId: "mem-1",
      fileUrl: `${USER}/b.png`,
      mimeType: "image/png",
    });
  });

  it("text와 asset이 둘 다 없으면 거부한다", async () => {
    const repo = stubRepo();
    await expect(createMemory(repo, { userId: USER })).rejects.toBeInstanceOf(EmptyMemoryError);
    expect(repo.insertMemory).not.toHaveBeenCalled();
  });

  it("공백뿐인 text는 없는 것으로 취급한다", async () => {
    const repo = stubRepo();
    await expect(createMemory(repo, { userId: USER, text: "   " })).rejects.toBeInstanceOf(
      EmptyMemoryError,
    );
  });

  it("남의 폴더 경로는 거부한다", async () => {
    const repo = stubRepo();
    await expect(
      createMemory(repo, {
        userId: USER,
        assetPaths: ["22222222-2222-2222-2222-222222222222/x.jpg"],
      }),
    ).rejects.toBeInstanceOf(ForeignAssetPathError);
    expect(repo.insertMemory).not.toHaveBeenCalled();
  });

  it("occurredAt을 그대로 넘긴다", async () => {
    const repo = stubRepo();
    await createMemory(repo, { userId: USER, text: "메모", occurredAt: "2026-03-01T09:00:00Z" });
    expect(repo.insertMemory).toHaveBeenCalledWith({
      userId: USER,
      rawText: "메모",
      occurredAt: "2026-03-01T09:00:00Z",
    });
  });
});

describe("사건 시각(occurredAt)", () => {
  const now = new Date("2026-07-29T12:00:00Z");

  it("과거는 받는다", () => {
    expect(() =>
      assertNotFuture("2026-07-15T09:00:00Z", now),
    ).not.toThrow();
  });

  it("먼 미래는 거부한다", () => {
    // 미래 기록을 받으면 '오늘'의 정의가 무너지고 아직 오지 않은 날에
    // 차이와 일기가 생긴다.
    expect(() => assertNotFuture("2026-07-30T00:00:00Z", now)).toThrow(
      FutureOccurrenceError,
    );
  });

  it("시계 어긋남만큼은 봐준다", () => {
    // 클라이언트 시계가 몇 분 빠른 것까지 막으면 정상 기록이 실패한다.
    expect(() =>
      assertNotFuture("2026-07-29T12:04:00Z", now),
    ).not.toThrow();
  });

  it("허용 오차를 넘으면 거부한다", () => {
    expect(() => assertNotFuture("2026-07-29T12:06:00Z", now)).toThrow(
      FutureOccurrenceError,
    );
  });

  it("값이 없으면 통과한다", () => {
    expect(() => assertNotFuture(undefined, now)).not.toThrow();
  });
});
