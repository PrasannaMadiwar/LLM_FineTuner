import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LLM Fine-Tuner",
  description: "Fine-tune open-source LLMs from a production web interface."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
