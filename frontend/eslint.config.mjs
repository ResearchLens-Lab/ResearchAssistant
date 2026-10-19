export default [
  {
    files: ["src/**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    rules: {
      "no-unreachable": "error",
      "no-dupe-keys": "error",
      "valid-typeof": "error",
      "no-unexpected-multiline": "error",
    },
  },
];
