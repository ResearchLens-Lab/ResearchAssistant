/**
 * Paper Models & Payloads
 * @typedef {Object} Paper
 * @property {string} id
 * @property {string} user_id
 * @property {string} title
 * @property {string[]} [authors]
 * @property {number} [publication_year]
 * @property {string} [venue]
 * @property {string} [doi]
 * @property {string} [source_url]
 * @property {string} [abstract]
 * @property {string} created_at
 * @property {string} updated_at
 */

/**
 * @typedef {Object} PaperSummaryResponse
 * @property {string} paper_id
 * @property {string} title
 * @property {string} answer
 * @property {Array} sources
 */

/**
 * @typedef {Object} PaperCompareResponse
 * @property {string[]} paper_ids
 * @property {string} answer
 * @property {Array} sources
 */
export {};
