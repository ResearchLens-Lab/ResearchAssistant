import test from "node:test";
import assert from "node:assert/strict";
import { isStrongPassword, normalizeUsername, passwordRequirements, validateUsername } from "./authValidation.mjs";

test("username validation canonicalizes case and rejects spaces, edge punctuation, and reserved names", () => {
  assert.equal(normalizeUsername("Research.User"), "research.user");
  assert.equal(validateUsername("Research.User"), "");
  assert.match(validateUsername(" bad "), /3–24 characters/);
  assert.match(validateUsername(".bad"), /3–24 characters/);
  assert.match(validateUsername("root"), /reserved/);
});

test("password rules align with the registration policy", () => {
  assert.equal(passwordRequirements("Short").length, 5);
  assert.equal(isStrongPassword("ResearchLens2026!"), true);
  assert.equal(isStrongPassword("researchlens2026!"), false);
});
