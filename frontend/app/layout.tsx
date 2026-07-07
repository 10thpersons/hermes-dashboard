import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { QueryProvider } from "@/components/query-provider";

export const metadata: Metadata = {
  title: "Hermes Dashboard",
  description: "Hermes Agent Operations Dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)]">
        <QueryProvider>
          <div className="flex flex-col md:flex-row h-screen overflow-hidden">
            <Sidebar />
            <main className="flex-1 overflow-y-auto p-6">
              {children}
            </main>
          </div>
        </QueryProvider>
      </body>
    </html>
  );
}
