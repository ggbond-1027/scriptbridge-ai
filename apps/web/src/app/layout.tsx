import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'NovelScripter - AI小说转剧本工具',
  description: '将小说智能转换为专业剧本格式，支持 API 与本地模型配置',
  icons: { icon: '/favicon.ico' },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
