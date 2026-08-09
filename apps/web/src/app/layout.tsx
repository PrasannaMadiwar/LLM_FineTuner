import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/context/AuthContext';
import { Sidebar } from '@/components/layout/Sidebar';
import { Header } from '@/components/layout/Header';

export const metadata: Metadata = {
  title: 'LLM Fine-Tuner | SaaS Platform',
  description:
    'Fine-tune open-source LLMs seamlessly without managing GPU infrastructure.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full bg-slate-50 font-sans text-slate-900 antialiased selection:bg-teal-100 selection:text-teal-900">
        <AuthProvider>
          <div className="flex min-h-screen">
            <Sidebar />
            <div className="flex-1 flex flex-col min-w-0">
              <Header />
              <main className="flex-1 p-8 max-w-7xl w-full mx-auto">
                {children}
              </main>
            </div>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
