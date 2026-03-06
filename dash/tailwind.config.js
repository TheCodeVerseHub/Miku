/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        discord: {
          dark: '#2F3136',
          gray: '#36393F',
          light: '#40444B',
          blue: '#5865F2',
          green: '#57F287',
          red: '#ED4245',
        },
      },
    },
  },
  plugins: [],
}
