import type { Metadata } from "next";
import { Toaster } from "@/components/ui/sonner";
import { TabBar } from "@/components/common/TabBar";
import "./globals.css";

export const metadata: Metadata = {
  title: "실은",
  description: "실은 아무것도 아니지 않았다",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className="h-full antialiased">
      <body className="flex min-h-full flex-col pb-14">
        <div className="flex-1">{children}</div>
        <TabBar />
        <Toaster />
      </body>
    </html>
  );
}
