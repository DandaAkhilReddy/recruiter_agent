import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Recruiter Agent",
  description:
    "AI-powered talent scouting & engagement — paste a JD, get a ranked shortlist with Match Score and Interest Score.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
