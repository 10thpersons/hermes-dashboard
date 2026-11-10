import type { Metadata } from 'next';
import './globals.css';
import { Sidebar } from '@/components/sidebar';
import { QueryProvider } from '@/components/query-provider';
import { ToastProvider } from '@/components/toast';

export const metadata: Metadata = {
  title: 'Hermes Dashboard',
  description: 'Hermes Agent Operations Dashboard',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        {/* Apply saved theme before React hydrates to prevent flash */}
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem('hermes-theme');if(t)document.documentElement.setAttribute('data-theme',t)}catch(e){}`,
          }}
        />
      </head>
      <body className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)]">
        <QueryProvider>
          <ToastProvider>
            <div className="flex flex-col md:flex-row h-screen overflow-hidden">
              <Sidebar />
              <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8 md:py-8">
                <div className="mx-auto w-full max-w-[1440px]">{children}</div>
              </main>
            </div>
          </ToastProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
