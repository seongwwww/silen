import type { Metadata } from "next";
import { DemoTodayLab } from "./_components/DemoTodayLab";
import { isDemoState } from "./fixtures";

export const metadata: Metadata = {
  title: "화면 상태 데모 · 실은",
};

export default async function DemoPage({
  searchParams,
}: {
  searchParams: Promise<{ state?: string }>;
}) {
  const { state } = await searchParams;
  return <DemoTodayLab initialState={isDemoState(state) ? state : "quiet"} />;
}
