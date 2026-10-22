import type { Config } from "tailwindcss";

// 9altitudes brand palette, shared with the Advanced Monitoring admin portal so
// the two operator tools look and feel like one product family.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          dark: "#333333",
          primary: "#2449B5",
          surface: "#f7f7f7",
          border: "#d9d9d9",
          muted: "#999999",
        },
      },
      fontFamily: {
        sans: [
          "system-ui",
          "-apple-system",
          '"Segoe UI"',
          "Roboto",
          '"Helvetica Neue"',
          "Arial",
          '"Noto Sans"',
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
} satisfies Config;
