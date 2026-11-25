import api from '../api';
import { ENDPOINTS } from './endpoints';

export async function listAgents(businessId) {
  const { data } = await api.get(ENDPOINTS.agents(businessId));
  return Array.isArray(data) ? data : [];
}

export async function createAgent(businessId, payload) {
  const { data } = await api.post(ENDPOINTS.agents(businessId), payload);
  return data;
}

export async function updateAgent(businessId, agentId, changes) {
  const { data } = await api.patch(ENDPOINTS.agent(businessId, agentId), changes);
  return data;
}

export async function updateAgentStatus(businessId, agentId, status) {
  const { data } = await api.patch(ENDPOINTS.agentStatus(businessId, agentId), { status });
  return data;
}

export async function deleteAgent(businessId, agentId) {
  await api.delete(ENDPOINTS.agent(businessId, agentId));
}

export async function chatWithAgent(businessId, agentId, { message, conversationId }) {
  const { data } = await api.post(ENDPOINTS.agentChat(businessId, agentId), {
    message,
    ...(conversationId ? { conversation_id: conversationId } : {}),
  });
  return data;
}

export async function listAgentConversations(businessId, agentId) {
  const { data } = await api.get(ENDPOINTS.agentConversations(businessId, agentId));
  return Array.isArray(data) ? data : [];
}

export async function getConversation(businessId, conversationId) {
  const { data } = await api.get(ENDPOINTS.conversation(businessId, conversationId));
  return data;
}

export async function deleteConversation(businessId, conversationId) {
  await api.delete(ENDPOINTS.conversation(businessId, conversationId));
}
