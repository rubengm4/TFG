/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./algovision/templates/**/*.html", "./algovision/**/*.py"],
  safelist: [
    // Added dynamically by `static/js/base.js`
    "-translate-x-full",
    "ml-0",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};
