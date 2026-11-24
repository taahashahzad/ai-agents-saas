import api from '../api';
import { ENDPOINTS } from './endpoints';

/**
 * Structured knowledge entries. Bodies contain ONLY title / category / content:
 * the backend rejects unknown fields (uid, role, business_id, ...) with 422.
 */

export async function listEntries(businessId, { limit = 100, cursor, category, signal } = {}) {
  const params = { limit };
  if (cursor) params.cursor = cursor;
  if (category) params.category = category;
  const { data } = await api.get(ENDPOINTS.knowledge(businessId), { params, signal });
  return {
    items: Array.isArray(data?.items) ? data.items : [],
    nextCursor: data?.next_cursor || null,
  };
}

export async function createEntry(businessId, { title, category, content }) {
  const { data } = await api.post(ENDPOINTS.knowledge(businessId), { title, category, content });
  return data;
}

/** `changes` is any non-empty subset of { title, category, content }. */
export async function updateEntry(businessId, entryId, changes) {
  const body = {};
  for (const key of ['title', 'category', 'content']) {
    if (changes[key] !== undefined) body[key] = changes[key];
  }
  const { data } = await api.patch(ENDPOINTS.knowledgeEntry(businessId, entryId), body);
  return data;
}

export async function deleteEntry(businessId, entryId) {
  await api.delete(ENDPOINTS.knowledgeEntry(businessId, entryId)); // 204 No Content
}
