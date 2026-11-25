import { useCallback, useEffect, useState } from 'react';
import Button from '../Button';
import Card from '../Card';
import ConfirmDialog from '../ConfirmDialog';
import ErrorAlert from '../ErrorAlert';
import Input from '../Input';
import Select from '../Select';
import Spinner from '../Spinner';
import {
  chatWithAgent,
  deleteConversation,
  getConversation,
  listAgentConversations,
} from '../../services/agentService';
import { formatDate } from '../../utils/constants';
import { getErrorMessage } from '../../utils/errors';

function Sources({ items }) {
  if (!items?.length) return null;
  return (
    <details className="mt-3 border-t border-slate-100 pt-2">
      <summary className="cursor-pointer text-xs font-medium text-indigo-700">
        Sources ({items.length})
      </summary>
      <ul className="mt-2 space-y-2">
        {items.map((source) => (
          <li key={source.chunk_id} className="rounded-lg bg-white p-3 text-xs text-slate-600">
            <div className="mb-1 flex justify-between gap-2 font-medium text-slate-700">
              <span>{source.document_name || source.title || 'Business knowledge'}</span>
              <span>{Number(source.score).toFixed(2)}</span>
            </div>
            <p className="whitespace-pre-wrap">{source.excerpt}</p>
          </li>
        ))}
      </ul>
    </details>
  );
}

export default function AgentPlayground({ businessId, agent }) {
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState('');
  const [messages, setMessages] = useState([]);
  const [message, setMessage] = useState('');
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [toDelete, setToDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const refreshConversations = useCallback(async () => {
    try {
      setConversations(await listAgentConversations(businessId, agent.agent_id));
    } catch (err) {
      setError(getErrorMessage(err, 'Could not load conversation history.'));
    } finally {
      setLoadingHistory(false);
    }
  }, [businessId, agent.agent_id]);

  useEffect(() => {
    refreshConversations();
  }, [refreshConversations]);

  const startNewConversation = () => {
    setConversationId('');
    setMessages([]);
    setMessage('');
    setError('');
  };

  const selectConversation = async (id) => {
    if (!id) {
      startNewConversation();
      return;
    }
    setError('');
    try {
      const detail = await getConversation(businessId, id);
      if (detail.conversation.agent_id !== agent.agent_id) {
        setError('That conversation belongs to a different agent.');
        return;
      }
      setConversationId(id);
      setMessages(detail.messages);
    } catch (err) {
      setError(getErrorMessage(err, 'Could not load this conversation.'));
    }
  };

  const submit = async (event) => {
    event.preventDefault();
    const text = message.trim();
    if (!text || sending) return;
    setSending(true);
    setError('');
    try {
      const result = await chatWithAgent(businessId, agent.agent_id, {
        message: text,
        conversationId: conversationId || undefined,
      });
      setConversationId(result.conversation_id);
      setMessages((previous) => [
        ...previous,
        result.user_message,
        result.assistant_message,
      ]);
      setMessage('');
      await refreshConversations();
    } catch (err) {
      setError(getErrorMessage(err, 'The agent could not respond.'));
    } finally {
      setSending(false);
    }
  };

  const confirmDelete = async () => {
    if (!conversationId) return;
    setDeleting(true);
    setError('');
    try {
      await deleteConversation(businessId, conversationId);
      startNewConversation();
      await refreshConversations();
    } catch (err) {
      setError(getErrorMessage(err, 'Could not delete this conversation.'));
    } finally {
      setDeleting(false);
      setToDelete(false);
    }
  };

  const historyOptions = conversations.map((item) => ({
    value: item.conversation_id,
    label: `${formatDate(item.updated_at)} · ${item.last_message_preview || 'Conversation'}`,
  }));

  return (
    <Card className="space-y-4">
      <div className="flex flex-col gap-3 border-b border-slate-100 pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h3 className="font-semibold text-slate-900">Test {agent.name}</h3>
          <p className="mt-1 text-xs text-slate-500">
            {agent.personality} · {agent.language} · {agent.model}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <div className="min-w-[14rem] flex-1">
            <Select
              id={`conversation-${agent.agent_id}`}
              label="Previous conversations"
              value={conversationId}
              onChange={(event) => selectConversation(event.target.value)}
              placeholder="New conversation"
              options={historyOptions}
              disabled={loadingHistory || sending}
            />
          </div>
          <Button variant="secondary" onClick={startNewConversation} disabled={sending}>
            New chat
          </Button>
          {conversationId && (
            <Button variant="danger" onClick={() => setToDelete(true)} disabled={sending}>
              Delete chat
            </Button>
          )}
        </div>
      </div>

      <ErrorAlert message={error} />

      {loadingHistory ? (
        <Spinner label="Loading conversation history..." />
      ) : (
        <div className="max-h-[28rem] space-y-3 overflow-y-auto rounded-lg bg-slate-50 p-4">
          {messages.length === 0 && agent.greeting && (
            <div className="max-w-[85%] rounded-xl rounded-bl-sm bg-white p-3 text-sm text-slate-700 shadow-sm">
              {agent.greeting}
            </div>
          )}
          {messages.map((item) => (
            <div
              key={item.message_id}
              className={`max-w-[90%] rounded-xl p-3 text-sm ${
                item.role === 'user'
                  ? 'ml-auto rounded-br-sm bg-indigo-600 text-white'
                  : 'rounded-bl-sm bg-white text-slate-800 shadow-sm'
              }`}
            >
              <p className="whitespace-pre-wrap">{item.content}</p>
              {item.role === 'assistant' && <Sources items={item.sources} />}
            </div>
          ))}
          {sending && (
            <div className="max-w-[85%] rounded-xl bg-white p-3 text-sm text-slate-500 shadow-sm">
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-indigo-600 align-middle" />
              <span className="ml-2">Thinking…</span>
            </div>
          )}
        </div>
      )}

      <form onSubmit={submit} className="flex gap-2">
        <Input
          id={`agent-message-${agent.agent_id}`}
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="Ask your agent a question"
          maxLength={4000}
          required
          disabled={sending}
          className="min-w-0 flex-1"
        />
        <Button type="submit" loading={sending} disabled={!message.trim()}>
          Send
        </Button>
      </form>

      <ConfirmDialog
        open={toDelete}
        title="Delete this conversation?"
        message="The conversation and its messages will be permanently deleted."
        confirmLabel="Delete conversation"
        loading={deleting}
        onConfirm={confirmDelete}
        onCancel={() => !deleting && setToDelete(false)}
      />
    </Card>
  );
}
