/**
 * Chat & Grounded Workbench Models
 * @typedef {Object} Message
 * @property {string} id
 * @property {string} conversation_id
 * @property {'user'|'assistant'|'system'} role
 * @property {string} content
 * @property {Array} [sources]
 * @property {string} created_at
 */

/**
 * @typedef {Object} Conversation
 * @property {string} id
 * @property {string} user_id
 * @property {string} [title]
 * @property {string[]} paper_ids
 * @property {string} created_at
 * @property {string} updated_at
 */
export {};
