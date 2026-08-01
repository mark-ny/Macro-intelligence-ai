import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0B0E14",
        panel: "#12161F",
        border: "#232838",
        ink: "#E8E3D8",
        muted: "#8B93A7",
        gold: "#C9A227",
        steel: "#4C8FC0",
        positive: "#5B8C5A",
        negative: "#B3503A",
      },
      fontFamily: {
        display: ["var(--font-display)"],
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
    },
  },
  plugins: [],
};
export default config;
