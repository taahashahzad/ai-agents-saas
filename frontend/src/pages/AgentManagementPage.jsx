import { useCallback, useEffect, useRef, useState } from 'react';
import Button from '../components/Button';
import Card from '../components/Card';
import ConfirmDialog from '../components/ConfirmDialog';
import EmptyState from '../components/EmptyState';
import ErrorAlert from '../components/ErrorAlert';
import Notice from '../components/Notice';
import RoleBadge from '../components/RoleBadge';
import Spinner from '../components/Spinner';
import AgentConfigModal from '../components/agents/AgentConfigModal';
import AgentPlayground from '../components/agents/AgentPlayground';
import { useBusiness } from '../hooks/useBusiness';
import { deleteAgent, listAgents, updateAgentStatus } from '../services/agentService';
import { formatDate } from '../utils/constants';
import { getErrorMessage } from '../utils/errors';

export default function AgentManagementPage() {
  const { activeBusiness, activeBusinessId, role, permissions, loading: businessLoading } = useBusiness();
  const [agents, setAgents] = useState([]);
  const [agentsBusinessId, setAgentsBusinessId] = useState('');
  const [selectedId, setSelectedId] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [notice, setNotice] = useState('');
  const [formAgent, setFormAgent] = useState(undefined);
  const [formBusinessId, setFormBusinessId] = useState('');
  const [toDelete, setToDelete] = useState(null);
  const [deleteBusinessId, setDeleteBusinessId] = useState('');
  const [busyId, setBusyId] = useState('');
  const requestRef = useRef(0);
  const businessIdRef = useRef(activeBusinessId);
  businessIdRef.current = activeBusinessId;

  const canManage = Boolean(permissions.manageAgents && activeBusiness?.status !== 'archived');
  const refresh = useCallback(async () => {
    if (!activeBusinessId || !permissions.manageAgents) {
      setAgents([]);
      setAgentsBusinessId(activeBusinessId || '');
      setLoading(false);
      return;
    }
    const requestId = ++requestRef.current;
    setLoading(true);
    setError('');
    try {
      const items = await listAgents(activeBusinessId);
      if (requestId !== requestRef.current) return;
      setAgents(items);
      setAgentsBusinessId(activeBusinessId);
      setSelectedId((previous) => items.some((item) => item.agent_id === previous)
        ? previous
        : items[0]?.agent_id || '');
    } catch (err) {
      if (requestId !== requestRef.current) return;
      setError(getErrorMessage(err, 'Could not load this business’s agents.'));
    } finally {
      if (requestId === requestRef.current) setLoading(false);
    }
  }, [activeBusinessId, permissions.manageAgents]);

  useEffect(() => {
    requestRef.current += 1;
    setAgents([]);
    setAgentsBusinessId('');
    setSelectedId('');
    setError('');
    setActionError('');
    setNotice('');
    setBusyId('');
    setFormAgent(undefined);
    setFormBusinessId('');
    setToDelete(null);
    setDeleteBusinessId('');
    refresh();
  }, [refresh, activeBusinessId]);

  const visibleAgents = agentsBusinessId === activeBusinessId ? agents : [];
  const selected = visibleAgents.find((agent) => agent.agent_id === selectedId) || null;
  const openForm = (agent) => {
    setFormBusinessId(activeBusinessId);
    setFormAgent(agent);
  };

  const handleSaved = (saved) => {
    if (businessIdRef.current !== formBusinessId) return;
    setAgents((previous) => {
      const exists = previous.some((item) => item.agent_id === saved.agent_id);
      return exists
        ? previous.map((item) => item.agent_id === saved.agent_id ? saved : item)
        : [saved, ...previous];
    });
    setSelectedId(saved.agent_id);
    setFormAgent(undefined);
    setFormBusinessId('');
    setNotice(`"${saved.name}" was ${formAgent ? 'updated' : 'created'}.`);
    setActionError('');
  };

  const toggleStatus = async (agent) => {
    const requestedBusinessId = activeBusinessId;
    const status = agent.status === 'active' ? 'inactive' : 'active';
    setBusyId(agent.agent_id);
    setActionError('');
    try {
      const updated = await updateAgentStatus(requestedBusinessId, agent.agent_id, status);
      if (businessIdRef.current !== requestedBusinessId) return;
      setAgents((previous) => previous.map((item) => item.agent_id === updated.agent_id ? updated : item));
      setNotice(`"${updated.name}" is now ${updated.status}.`);
    } catch (err) {
      if (businessIdRef.current === requestedBusinessId) {
        setActionError(getErrorMessage(err, 'Could not change agent status.'));
      }
    } finally {
      if (businessIdRef.current === requestedBusinessId) setBusyId('');
    }
  };

  const confirmDelete = async () => {
    if (!toDelete || deleteBusinessId !== activeBusinessId) return;
    const requestedBusinessId = activeBusinessId;
    setBusyId(toDelete.agent_id);
    setActionError('');
    try {
      await deleteAgent(requestedBusinessId, toDelete.agent_id);
      if (businessIdRef.current !== requestedBusinessId) return;
      setAgents((previous) => previous.filter((item) => item.agent_id !== toDelete.agent_id));
      if (selectedId === toDelete.agent_id) setSelectedId('');
      setNotice(`"${toDelete.name}" and its conversations were deleted.`);
    } catch (err) {
      if (businessIdRef.current === requestedBusinessId) {
        setActionError(getErrorMessage(err, 'Could not delete this agent.'));
      }
    } finally {
      if (businessIdRef.current === requestedBusinessId) {
        setBusyId('');
        setToDelete(null);
        setDeleteBusinessId('');
      }
    }
  };

  if (businessLoading) return <Spinner label="Loading..." />;
  if (!activeBusiness) {
    return (
      <EmptyState
        title="No business selected"
        description="Create a business or accept an invitation before creating an agent."
      />
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">AI Agents</h1>
          <p className="mt-1 text-sm text-slate-500">
            Configure and test assistants grounded in {activeBusiness.name}&apos;s knowledge.
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm">
          <span className="max-w-[12rem] truncate font-medium text-slate-900">{activeBusiness.name}</span>
          <RoleBadge role={role} />
        </div>
      </header>

      {activeBusiness.status === 'archived' && (
        <Notice type="warning">This business is archived; agents are read-only.</Notice>
      )}
      {!permissions.manageAgents && (
        <Notice type="info">Owners and admins can manage and test business agents.</Notice>
      )}
      {notice && <Notice onDismiss={() => setNotice('')}>{notice}</Notice>}
      <ErrorAlert message={actionError} />

      {loading ? (
        <Spinner label="Loading agents..." />
      ) : error ? (
        <ErrorAlert message={error} onRetry={refresh} />
      ) : visibleAgents.length === 0 ? (
        <EmptyState
          title="No agents yet"
          description="Create a business assistant, configure its behavior, then test it against this business’s knowledge."
          action={canManage ? <Button onClick={() => openForm(null)}>Create agent</Button> : undefined}
        />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(16rem,0.8fr)_minmax(0,1.5fr)]">
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-slate-900">Your agents</h2>
              {canManage && <Button onClick={() => openForm(null)}>Create agent</Button>}
            </div>
            {visibleAgents.map((agent) => (
              <Card
                key={agent.agent_id}
                className={`cursor-pointer transition ${
                  selectedId === agent.agent_id ? 'border-indigo-300 ring-2 ring-indigo-100' : 'hover:border-slate-300'
                }`}
              >
                <button
                  type="button"
                  onClick={() => setSelectedId(agent.agent_id)}
                  className="w-full text-left"
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-semibold text-slate-900">{agent.name}</span>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      agent.status === 'active'
                        ? 'bg-emerald-50 text-emerald-700'
                        : 'bg-slate-100 text-slate-600'
                    }`}>
                      {agent.status}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{agent.agent_type} · Created {formatDate(agent.created_at)}</p>
                  {agent.description && <p className="mt-2 line-clamp-2 text-sm text-slate-600">{agent.description}</p>}
                </button>
                {canManage && (
                  <div className="mt-3 flex flex-wrap gap-2 border-t border-slate-100 pt-3">
                    <button
                      type="button"
                      onClick={() => openForm(agent)}
                      className="text-xs font-medium text-indigo-600 hover:text-indigo-700"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      disabled={busyId === agent.agent_id}
                      onClick={() => toggleStatus(agent)}
                      className="text-xs font-medium text-slate-600 hover:text-slate-900 disabled:opacity-50"
                    >
                      {agent.status === 'active' ? 'Deactivate' : 'Activate'}
                    </button>
                    <button
                      type="button"
                      disabled={Boolean(busyId)}
                      onClick={() => {
                        setDeleteBusinessId(activeBusinessId);
                        setToDelete(agent);
                      }}
                      className="text-xs font-medium text-red-600 hover:text-red-700 disabled:opacity-50"
                    >
                      Delete
                    </button>
                  </div>
                )}
              </Card>
            ))}
          </section>

          <section className="space-y-4">
            {selected ? (
              <>
                <Card>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="text-lg font-semibold text-slate-900">{selected.name}</h2>
                      <p className="mt-1 text-sm text-slate-500">
                        {selected.personality} · {selected.language} · {selected.response_length} responses
                      </p>
                    </div>
                    <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700">
                      {selected.model}
                    </span>
                  </div>
                  <p className="mt-4 whitespace-pre-wrap text-sm text-slate-700">{selected.instructions}</p>
                </Card>
                {selected.status === 'active' ? (
                  <AgentPlayground
                    key={`${activeBusinessId}-${selected.agent_id}`}
                    businessId={activeBusinessId}
                    agent={selected}
                  />
                ) : (
                  <Notice type="warning">Activate this agent before testing it in the playground.</Notice>
                )}
              </>
            ) : (
              <Card><p className="text-sm text-slate-500">Select an agent to view its configuration and playground.</p></Card>
            )}
          </section>
        </div>
      )}

      {formAgent !== undefined && formBusinessId === activeBusinessId && (
        <AgentConfigModal
          businessId={activeBusinessId}
          agent={formAgent}
          onClose={() => {
            setFormAgent(undefined);
            setFormBusinessId('');
          }}
          onSaved={handleSaved}
        />
      )}
      <ConfirmDialog
        open={Boolean(toDelete && deleteBusinessId === activeBusinessId)}
        title="Delete this agent?"
        message={`"${toDelete?.name || ''}" and all conversations and messages attached to it will be permanently deleted.`}
        confirmLabel="Delete agent"
        loading={Boolean(busyId)}
        onConfirm={confirmDelete}
        onCancel={() => !busyId && setToDelete(null)}
      />
    </div>
  );
}
