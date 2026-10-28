import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Australian Regulatory AI Assistant",
  description: "Explore Australian consumer guidance with traceable sources and cited evidence.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
