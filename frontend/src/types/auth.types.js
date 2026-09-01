/**
 * Authentication Models & Payloads
 * @typedef {Object} User
 * @property {string} id
 * @property {string} email
 * @property {string} [full_name]
 * @property {boolean} is_active
 * @property {boolean} is_verified
 * @property {string} created_at
 * @property {string} updated_at
 */

/**
 * @typedef {Object} TokenResponse
 * @property {string} access_token
 * @property {string} refresh_token
 * @property {string} token_type
 * @property {number} expires_in
 */
export {};
