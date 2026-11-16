"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

export default function LandingThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const preferred = localStorage.getItem("firelens-dark") === "1";
    document.documentElement.classList.toggle("dark", preferred);
    setDark(preferred);
  }, []);
  return <button className="landing-theme-button" type="button" aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} onClick={() => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("firelens-dark", next ? "1" : "0");
  }}>{dark ? <Sun size={17} /> : <Moon size={17} />}</button>;
}
