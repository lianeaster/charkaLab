/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Кремове тло логотипу
        cream: "#f8f3ea",
        // Бурштиново-помаранчева рідина (основний колір)
        charka: {
          50: "#fdf6ec",
          100: "#f9e8d2",
          200: "#f0cba0",
          300: "#e6ad6e",
          400: "#dd9446",
          500: "#d07c2b",
          600: "#b5621f",
          700: "#8f4a1b",
        },
        // Темно-винний (мароон) — акценти
        wine: {
          50: "#fbeceb",
          100: "#f3d2cf",
          200: "#e3a9a4",
          500: "#8e2b25",
          600: "#74211d",
          700: "#5c1a18",
        },
      },
    },
  },
  plugins: [],
};
