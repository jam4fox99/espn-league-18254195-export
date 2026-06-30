import type { Metadata } from "next";
import { Chakra_Petch, JetBrains_Mono, Rubik, Saira_Condensed } from "next/font/google";
import type { ReactNode } from "react";
import "./globals.css";
import "./app-shell.css";
import "./styles.css";
import "./product-surfaces.css";
import "./fantasy-theme.css";

const rubik = Rubik({
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500", "600", "700", "800", "900"],
  variable: "--font-sans"
});

const jetBrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500", "600", "700"],
  variable: "--font-mono"
});

// Condensed display face for names/headers/OVR — the 2K / MyGM-Menu look.
const sairaCondensed = Saira_Condensed({
  subsets: ["latin"],
  display: "swap",
  weight: ["500", "600", "700", "800"],
  variable: "--font-saira"
});

// Technical mono-ish face for kicker labels + stat chips.
const chakraPetch = Chakra_Petch({
  subsets: ["latin"],
  display: "swap",
  weight: ["500", "600", "700"],
  variable: "--font-chakra"
});

export const metadata: Metadata = {
  title: "MyGM · Retrospective GM Rating",
  description: "Invite-gated ESPN import and retrospective GM rating workspace."
};

export default function RootLayout({ children }: { readonly children: ReactNode }) {
  return (
    <html
      lang="en"
      className={`${rubik.variable} ${jetBrainsMono.variable} ${sairaCondensed.variable} ${chakraPetch.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
