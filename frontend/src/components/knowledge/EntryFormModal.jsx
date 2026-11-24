import { useState } from 'react';
import Button from '../Button';
import ErrorAlert from '../ErrorAlert';
import Input from '../Input';
import Modal from '../Modal';
import Textarea from '../Textarea';
import { createEntry, updateEntry } from '../../services/knowledgeService';
import { ENTRY_LIMITS, categorySuggestions, validateEntry } from '../../utils/knowledge';
import { getErrorCode, getErrorMessage } from '../../utils/errors';

/**
 * Reusable create/edit form: Title, Category, Content. Nothing is specific to a
 * business type; `businessType` only picks which category quick-picks to suggest.
 * Render conditionally (`{open && <EntryFormModal .../>}`) so state resets each time.
 */
export default function EntryFormModal({ businessId, businessType, entry, onClose, onSaved, onMissing }) {
  const editing = Boolean(entry);
  const [values, setValues] = useState({
    title: entry?.title || '',
    category: entry?.category || '',
    content: entry?.content || '',
  });
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState('');
  const [saving, setSaving] = useState(false);

  const change = (e) => {
    const { name, value } = e.target;
    setValues((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: '' }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (saving) return;
    const found = validateEntry(values);
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    const clean = {
      title: values.title.trim(),
      category: values.category.trim(),
      content: values.content.trim(),
    };

    setSaving(true);
    setServerError('');
    try {
      if (editing) {
        // PATCH accepts any non-empty subset: send only what actually changed.
        const changes = {};
        for (const key of ['title', 'category', 'content']) {
          const before = key === 'category' ? String(entry[key] || '').toLowerCase() : entry[key];
          const after = key === 'category' ? clean[key].toLowerCase() : clean[key];
          if (after !== before) changes[key] = clean[key];
        }
        if (Object.keys(changes).length === 0) {
          onClose();
          return;
        }
        onSaved(await updateEntry(businessId, entry.entry_id, changes), 'edit');
      } else {
        onSaved(await createEntry(businessId, clean), 'create');
      }
    } catch (err) {
      if (getErrorCode(err) === 'entry_not_found') {
        onMissing?.(getErrorMessage(err));
        return;
      }
      setServerError(getErrorMessage(err, 'Failed to save the entry.'));
      setSaving(false);
    }
  };

  const suggestions = categorySuggestions(businessType);

  return (
    <Modal
      title={editing ? 'Edit information' : 'Add information'}
      description="Structured facts your AI agents can use about this business."
      onClose={onClose}
      locked={saving}
      closeOnBackdrop={false}
      maxWidth="max-w-xl"
    >
      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        <ErrorAlert message={serverError} />
        <Input
          id="entry-title"
          name="title"
          label="Title"
          placeholder="e.g. Opening hours"
          maxLength={ENTRY_LIMITS.title + 50}
          value={values.title}
          onChange={change}
          error={errors.title}
          disabled={saving}
          autoFocus
        />
        <div>
          <Input
            id="entry-category"
            name="category"
            label="Category"
            placeholder="e.g. hours, menu, policies, faq"
            list="entry-category-suggestions"
            autoComplete="off"
            value={values.category}
            onChange={change}
            error={errors.category}
            disabled={saving}
          />
          <datalist id="entry-category-suggestions">
            {suggestions.map((s) => (
              <option key={s} value={s} />
            ))}
          </datalist>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {suggestions.map((s) => (
              <button
                key={s}
                type="button"
                disabled={saving}
                onClick={() => {
                  setValues((prev) => ({ ...prev, category: s }));
                  setErrors((prev) => ({ ...prev, category: '' }));
                }}
                className="rounded-full border border-slate-200 bg-white px-2.5 py-0.5 text-xs text-slate-600 hover:border-indigo-300 hover:text-indigo-700 disabled:opacity-50"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
        <div>
          <Textarea
            id="entry-content"
            name="content"
            label="Content"
            rows={7}
            placeholder="Write the information exactly as you want the agent to know it."
            value={values.content}
            onChange={change}
            error={errors.content}
            disabled={saving}
          />
          <p
            className={`mt-1 text-right text-xs ${
              values.content.length > ENTRY_LIMITS.content ? 'text-red-600' : 'text-slate-400'
            }`}
          >
            {values.content.length.toLocaleString()} / {ENTRY_LIMITS.content.toLocaleString()}
          </p>
        </div>
        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Button variant="secondary" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" loading={saving}>
            {editing ? 'Save changes' : 'Add information'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
