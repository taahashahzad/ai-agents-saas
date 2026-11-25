/**
 * Single source of truth for backend paths.
 * Phase 1: only POST /api/v1/users/me was specified; the rest were assumed.
 * Phase 2: membership / invitation / role paths below follow the proposed
 * contract. Request/response SCHEMAS are not yet confirmed with the backend
 * developer; if they differ, adjust src/services/memberService.js and
 * src/utils/permissions.js (getBusinessRole). Paths live ONLY in this file.
 */
const API_PREFIX = '/api/v1';
const enc = encodeURIComponent;

export const ENDPOINTS = {
  // Current user
  syncUser: `${API_PREFIX}/users/me`, // POST
  getUser: `${API_PREFIX}/users/me`, // GET

  // Businesses
  businesses: `${API_PREFIX}/businesses`, // GET (list), POST (create)
  business: (id) => `${API_PREFIX}/businesses/${enc(id)}`, // GET, PUT
  archiveBusiness: (id) => `${API_PREFIX}/businesses/${enc(id)}/archive`, // POST

  // Business membership
  members: (businessId) => `${API_PREFIX}/businesses/${enc(businessId)}/members`, // GET
  member: (businessId, uid) =>
    `${API_PREFIX}/businesses/${enc(businessId)}/members/${enc(uid)}`, // DELETE
  memberRole: (businessId, uid) =>
    `${API_PREFIX}/businesses/${enc(businessId)}/members/${enc(uid)}/role`, // PATCH
  businessInvitations: (businessId) =>
    `${API_PREFIX}/businesses/${enc(businessId)}/invitations`, // GET, POST

  // Knowledge Base (Phase 3, final backend contract). The business is identified
  // ONLY by the id in the URL; the server derives user and role from the token.
  documents: (businessId) => `${API_PREFIX}/businesses/${enc(businessId)}/documents`, // GET, POST (multipart)
  document: (businessId, documentId) =>
    `${API_PREFIX}/businesses/${enc(businessId)}/documents/${enc(documentId)}`, // GET, DELETE
  downloadDocument: (businessId, documentId) =>
    `${API_PREFIX}/businesses/${enc(businessId)}/documents/${enc(documentId)}/download`, // GET (binary)
  retryDocument: (businessId, documentId) =>
    `${API_PREFIX}/businesses/${enc(businessId)}/documents/${enc(documentId)}/retry`, // POST
  indexDocument: (businessId, documentId) =>
    `${API_PREFIX}/businesses/${enc(businessId)}/documents/${enc(documentId)}/index`, // POST
  reindexDocument: (businessId, documentId) =>
    `${API_PREFIX}/businesses/${enc(businessId)}/documents/${enc(documentId)}/reindex`, // POST
  documentIndexStatus: (businessId, documentId) =>
    `${API_PREFIX}/businesses/${enc(businessId)}/documents/${enc(documentId)}/index-status`, // GET
  knowledge: (businessId) => `${API_PREFIX}/businesses/${enc(businessId)}/knowledge`, // GET, POST
  knowledgeEntry: (businessId, entryId) =>
    `${API_PREFIX}/businesses/${enc(businessId)}/knowledge/${enc(entryId)}`, // PATCH, DELETE
  indexKnowledgeEntry: (businessId, entryId) =>
    `${API_PREFIX}/businesses/${enc(businessId)}/knowledge/${enc(entryId)}/index`, // POST
  ragQuery: (businessId) => `${API_PREFIX}/businesses/${enc(businessId)}/rag/query`, // POST
  agents: (businessId) => `${API_PREFIX}/businesses/${enc(businessId)}/agents`, // GET, POST
  agent: (businessId, agentId) =>
    `${API_PREFIX}/businesses/${enc(businessId)}/agents/${enc(agentId)}`, // GET, PATCH, DELETE
  agentStatus: (businessId, agentId) =>
    `${API_PREFIX}/businesses/${enc(businessId)}/agents/${enc(agentId)}/status`, // PATCH
  agentChat: (businessId, agentId) =>
    `${API_PREFIX}/businesses/${enc(businessId)}/agents/${enc(agentId)}/chat`, // POST
  agentConversations: (businessId, agentId) =>
    `${API_PREFIX}/businesses/${enc(businessId)}/agents/${enc(agentId)}/conversations`, // GET
  conversation: (businessId, conversationId) =>
    `${API_PREFIX}/businesses/${enc(businessId)}/conversations/${enc(conversationId)}`, // GET, DELETE

  // Invitations addressed to the signed-in user
  myInvitations: `${API_PREFIX}/invitations`, // GET
  acceptInvitation: (id) => `${API_PREFIX}/invitations/${enc(id)}/accept`, // POST
  declineInvitation: (id) => `${API_PREFIX}/invitations/${enc(id)}/decline`, // POST
};
