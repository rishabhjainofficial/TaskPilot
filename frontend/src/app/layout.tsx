import "./globals.css";
import QueryProvider from "@/lib/query-provider";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "TaskPilot SaaS - AI Task Assistant",
  description: "Production-grade, multi-tenant AI task management platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
