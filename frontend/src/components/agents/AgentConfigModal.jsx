import { useState } from 'react';
import Button from '../Button';
import ErrorAlert from '../ErrorAlert';
import Input from '../Input';
import Modal from '../Modal';
import Select from '../Select';
import Textarea from '../Textarea';
import { createAgent, updateAgent } from '../../services/agentService';
import { getErrorMessage } from '../../utils/errors';

const TYPE_SUGGESTIONS = [
  'General Business Assistant',
  'Restaurant Assistant',
  'Customer Support Agent',
  'Sales Assistant',
  'Clinic Information Assistant',
  'School Information Assistant',
];

export default function AgentConfigModal({ businessId, agent, onClose, onSaved }) {
  const [values, setValues] = useState({
    name: agent?.name || '',
    description: agent?.description || '',
    agent_type: agent?.agent_type || 'General Business Assistant',
    instructions: agent?.instructions || '',
    personality: agent?.personality || 'Friendly',
    greeting: agent?.greeting || 'Hello! How can I help you?',
    language: agent?.language || 'English',
    model: agent?.model || 'default',
    temperature: String(agent?.temperature ?? 0.2),
    response_length: agent?.response_length || 'standard',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const set = (key) => (event) => setValues((current) => ({ ...current, [key]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    const payload = {
      ...values,
      temperature: Number(values.temperature),
    };
    try {
      const saved = agent
        ? await updateAgent(businessId, agent.agent_id, payload)
        : await createAgent(businessId, payload);
      onSaved(saved);
    } catch (err) {
      setError(getErrorMessage(err, 'Could not save this agent.'));
    } finally {
      setSaving(false);
    }
  };

  const modelOptions = [{ value: 'default', label: 'Backend-approved default model' }];
  if (agent?.model && agent.model !== 'default') {
    modelOptions.push({ value: agent.model, label: `Current approved model (${agent.model})` });
  }

  return (
    <Modal
      title={agent ? 'Edit agent' : 'Create agent'}
      description="Configure the assistant for this business. The backend controls the available AI model."
      onClose={onClose}
      locked={saving}
      maxWidth="max-w-2xl"
    >
      <form onSubmit={submit} className="space-y-4">
        <ErrorAlert message={error} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            id="agent-name"
            label="Agent name"
            value={values.name}
            onChange={set('name')}
            maxLength={100}
            required
          />
          <div>
            <label htmlFor="agent-type" className="mb-1.5 block text-sm font-medium text-slate-700">Agent type</label>
            <input
              id="agent-type"
              list="agent-type-options"
              value={values.agent_type}
              onChange={set('agent_type')}
              maxLength={80}
              required
              className="block w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
            />
            <datalist id="agent-type-options">
              {TYPE_SUGGESTIONS.map((type) => <option key={type} value={type} />)}
            </datalist>
          </div>
        </div>
        <Input
          id="agent-description"
          label="Description"
          value={values.description}
          onChange={set('description')}
          maxLength={1000}
        />
        <div>
          <Textarea
            id="agent-instructions"
            label="System instructions"
            value={values.instructions}
            onChange={set('instructions')}
            rows={5}
            maxLength={6000}
            required
          />
          <p className="mt-1 text-xs text-slate-500">
            Describe the assistant&apos;s role. Platform safety and business knowledge grounding remain enforced.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            id="agent-personality"
            label="Personality"
            value={values.personality}
            onChange={set('personality')}
            maxLength={80}
            required
          />
          <Input
            id="agent-language"
            label="Preferred response language"
            value={values.language}
            onChange={set('language')}
            maxLength={60}
            required
          />
        </div>
        <Textarea
          id="agent-greeting"
          label="Greeting message"
          value={values.greeting}
          onChange={set('greeting')}
          rows={2}
          maxLength={1000}
        />
        <div className="grid gap-4 sm:grid-cols-3">
          <Select
            id="agent-model"
            label="AI model"
            value={values.model}
            onChange={set('model')}
            options={modelOptions}
          />
          <Input
            id="agent-temperature"
            label="Temperature (0–1)"
            type="number"
            min="0"
            max="1"
            step="0.1"
            value={values.temperature}
            onChange={set('temperature')}
            required
          />
          <Select
            id="agent-response-length"
            label="Response length"
            value={values.response_length}
            onChange={set('response_length')}
            options={[
              { value: 'short', label: 'Short' },
              { value: 'standard', label: 'Standard' },
              { value: 'long', label: 'Long' },
            ]}
          />
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="secondary" onClick={onClose} disabled={saving}>Cancel</Button>
          <Button type="submit" loading={saving}>{agent ? 'Save changes' : 'Create agent'}</Button>
        </div>
      </form>
    </Modal>
  );
}
