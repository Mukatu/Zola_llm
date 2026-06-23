import type { Metadata, Viewport } from "next";
import "./globals.css";
import { ConfigProvider } from "@/components/ConfigProvider";
import { AppShell } from "@/components/AppShell";
import { Pwa } from "@/components/Pwa";

export const metadata: Metadata = {
  title: "ZolaOS",
  description: "Plateforme IA souveraine — pilotage d'entreprise (Afrique centrale)",
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = {
  themeColor: "#0B5FFF",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>
        <ConfigProvider>
          <AppShell>{children}</AppShell>
          <Pwa />
        </ConfigProvider>
      </body>
    </html>
  );
}
