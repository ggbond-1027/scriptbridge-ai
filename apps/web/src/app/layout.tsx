import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ScriptBridge AI",
  description: "AI 小说转剧本结构化工作台",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
