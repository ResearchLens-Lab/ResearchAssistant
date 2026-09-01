/**
 * Document Models
 * @typedef {'uploaded'|'processing'|'indexed'|'failed'} DocumentProcessingStatus
 *
 * @typedef {Object} DocumentResponse
 * @property {string} id
 * @property {string} paper_id
 * @property {string} filename
 * @property {number} file_size
 * @property {DocumentProcessingStatus} processing_status
 * @property {number} [chunk_count]
 * @property {string} [error_message]
 * @property {string} created_at
 * @property {string} updated_at
 */
export {};
