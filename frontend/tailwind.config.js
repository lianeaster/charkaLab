/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        macerate: {
          50: "#fdf4f5",
          100: "#fbe8eb",
          500: "#b4475c",
          600: "#9a3a4d",
          700: "#7d2f3f",
        },
      },
    },
  },
  plugins: [],
};
