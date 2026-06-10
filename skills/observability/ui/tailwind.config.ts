import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx,js,jsx,html}'],
  darkMode: 'media',
  theme: {
    extend: {},
  },
  plugins: [],
};

export default config;
