export const USERNAME_PATTERN = /^[a-z0-9](?:[a-z0-9._-]{1,22}[a-z0-9])$/i;
export const RESERVED_USERNAMES = new Set(["admin", "support", "root"]);

export function normalizeUsername(value = "") {
  return value.toLowerCase();
}

export function validateUsername(value = "") {
  const username = normalizeUsername(value);
  if (!username) return "Choose a username.";
  if (!USERNAME_PATTERN.test(username)) return "Use 3–24 characters with the allowed symbols; punctuation must be internal.";
  if (RESERVED_USERNAMES.has(username)) return "This username is reserved. Choose another.";
  return "";
}

export function passwordRequirements(password = "") {
  return [
    { label: "At least 12 characters", valid: password.length >= 12 },
    { label: "Uppercase letter", valid: /[A-Z]/.test(password) },
    { label: "Lowercase letter", valid: /[a-z]/.test(password) },
    { label: "Number", valid: /\d/.test(password) },
    { label: "Special character", valid: /[^A-Za-z0-9]/.test(password) },
  ];
}

export function isStrongPassword(password = "") {
  return passwordRequirements(password).every((requirement) => requirement.valid) && new TextEncoder().encode(password).length <= 72;
}
