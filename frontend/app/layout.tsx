import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Mahjong Review Helper",
  description: "日本麻將復盤系統 — chess.com 風格逐手點評",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-Hant">
      <body>{children}</body>
    </html>
  );
}
