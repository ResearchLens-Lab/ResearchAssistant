/**
 * API Response Envelopes & Pagination
 * @typedef {Object} PageResponse
 * @property {Array} items
 * @property {number} total
 * @property {number} page
 * @property {number} page_size
 * @property {number} total_pages
 */

/**
 * @typedef {Object} ApiErrorDetail
 * @property {string} code
 * @property {string} message
 * @property {string} [request_id]
 * @property {Array} [details]
 */

/**
 * @typedef {Object} ApiErrorResponse
 * @property {ApiErrorDetail} error
 */
export {};
