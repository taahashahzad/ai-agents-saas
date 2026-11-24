import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Button from '../Button';
import Card from '../Card';
import ConfirmDialog from '../ConfirmDialog';
import EmptyState from '../EmptyState';
import ErrorAlert from '../ErrorAlert';
import Notice from '../Notice';
import { CardGridSkeleton } from '../Skeleton';
import EntryFormModal from './EntryFormModal';
import EntryViewModal from './EntryViewModal';
import { deleteEntry, listEntries } from '../../services/knowledgeService';
import { formatDate } from '../../utils/constants';
import { getErrorMessage, getStatus, isCanceled } from '../../utils/errors';

/**
 * Structured knowledge entries (Title / Category / Content) for ONE business.
 * Free-form categories keep this usable for any business type.
 * Remounted on business switch by the dashboard layout; in-flight requests are aborted on cleanup.
 */
export default function BusinessInfoTab({ businessId, businessName, businessType, canWrite, readOnlyReason }) {
  const [entries, setEntries] = useState([]);
  const [nextCursor, setNextCursor] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');

  const [filter, setFilter] = useState('all');
  const [formState, setFormState] = useState(null); // { entry? } while the add/edit dialog is open
  const [viewing, setViewing] = useState(null);
  const [toDelete, setToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [notice, setNotice] = useState('');
  const [actionError, setActionError] = useState('');

  const abortRef = useRef(null);
  const requestRef = useRef(0);

  const fetchFirstPage = useCallback(
    async ({ silent = false } = {}) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const id = ++requestRef.current;
      if (!silent) setLoading(true);
      setError('');
      try {
        const page = await listEntries(businessId, { signal: controller.signal });
        if (id !== requestRef.current) return;
        setEntries(page.items);
        setNextCursor(page.nextCursor);
      } catch (err) {
        if (isCanceled(err) || id !== requestRef.current) return;
        if (!silent) setEntries([]);
        setError(getErrorMessage(err, 'Failed to load business information.'));
      } finally {
        if (id === requestRef.current) setLoading(false);
      }
    },
    [businessId]
  );

  useEffect(() => {
    fetchFirstPage();
    return () => {
      requestRef.current += 1;
      abortRef.current?.abort();
    };
  }, [fetchFirstPage]);

  const loadMore = async () => {
    if (!nextCursor || loadingMore) return;
    const id = requestRef.current;
    setLoadingMore(true);
    try {
      const page = await listEntries(businessId, { cursor: nextCursor, signal: abortRef.current?.signal });
      if (id !== requestRef.current) return;
      setEntries((prev) => [...prev, ...page.items.filter((e) => !prev.some((p) => p.entry_id === e.entry_id))]);
      setNextCursor(page.nextCursor);
    } catch (err) {
      if (!isCanceled(err)) setActionError(getErrorMessage(err, 'Failed to load more entries.'));
    } finally {
      setLoadingMore(false);
    }
  };

  const categories = useMemo(() => {
    const counts = new Map();
    entries.forEach((e) => counts.set(e.category, (counts.get(e.category) || 0) + 1));
    return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [entries]);

  const activeFilter = filter === 'all' || categories.some(([c]) => c === filter) ? filter : 'all';
  const visible = activeFilter === 'all' ? entries : entries.filter((e) => e.category === activeFilter);

  const handleSaved = (saved, mode) => {
    setFormState(null);
    setViewing(null);
    setActionError('');
    if (mode === 'create') {
      setEntries((prev) => [saved, ...prev]);
      setNotice(`"${saved.title}" was added.`);
    } else {
      setEntries((prev) => prev.map((e) => (e.entry_id === saved.entry_id ? saved : e)));
      setNotice(`"${saved.title}" was updated.`);
    }
  };

  const handleMissing = async (message) => {
    setFormState(null);
    setViewing(null);
    setActionError(message || 'That entry no longer exists.');
    await fetchFirstPage({ silent: true });
  };

  const confirmDelete = async () => {
    if (!toDelete) return;
    const target = toDelete;
    setDeleting(true);
    setActionError('');
    setNotice('');
    try {
      await deleteEntry(businessId, target.entry_id);
      setEntries((prev) => prev.filter((e) => e.entry_id !== target.entry_id));
      setNotice(`"${target.title}" was deleted.`);
      setViewing(null);
    } catch (err) {
      setActionError(getErrorMessage(err, 'Failed to delete the entry.'));
      if (getStatus(err) === 404) await fetchFirstPage({ silent: true });
    } finally {
      setToDelete(null);
      setDeleting(false);
    }
  };

  const addButton = canWrite ? <Button onClick={() => setFormState({})}>Add information</Button> : undefined;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-slate-500">
          Facts, policies and FAQs about <span className="font-medium text-slate-700">{businessName}</span>, written by your team.
        </p>
        {addButton && <div className="shrink-0">{addButton}</div>}
      </div>

      {!canWrite && readOnlyReason && <Notice type="info">{readOnlyReason}</Notice>}
      <Notice type="success" onDismiss={() => setNotice('')}>
        {notice}
      </Notice>
      <ErrorAlert message={actionError} />

      {loading ? (
        <CardGridSkeleton />
      ) : error ? (
        <ErrorAlert message={error} onRetry={() => fetchFirstPage()} />
      ) : entries.length === 0 ? (
        <EmptyState
          title="Your Knowledge Base is empty"
          description={
            canWrite
              ? 'Upload documents or add business information to get started.'
              : 'No business information has been added yet. An owner or admin can add it.'
          }
          action={addButton}
        />
      ) : (
        <>
          {categories.length > 1 && (
            <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by category">
              {[['all', entries.length], ...categories].map(([cat, count]) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setFilter(cat)}
                  aria-pressed={activeFilter === cat}
                  className={`rounded-full border px-3 py-1 text-xs font-medium capitalize transition ${
                    activeFilter === cat
                      ? 'border-indigo-600 bg-indigo-600 text-white'
                      : 'border-slate-200 bg-white text-slate-600 hover:border-indigo-300'
                  }`}
                >
                  {cat === 'all' ? 'All' : cat} <span className="opacity-70">({count})</span>
                </button>
              ))}
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {visible.map((entry) => (
              <Card key={entry.entry_id} className="flex flex-col !p-5">
                <div className="flex items-start justify-between gap-3">
                  <button
                    type="button"
                    onClick={() => setViewing(entry)}
                    className="min-w-0 text-left text-base font-semibold text-slate-900 hover:text-indigo-600"
                  >
                    <span className="line-clamp-2 break-words">{entry.title}</span>
                  </button>
                  <span className="shrink-0 rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-medium capitalize text-indigo-700">
                    {entry.category}
                  </span>
                </div>
                <p className="mt-2 line-clamp-4 flex-1 whitespace-pre-line break-words text-sm text-slate-500">
                  {entry.content}
                </p>
                <div className="mt-4 flex items-center justify-between gap-2 border-t border-slate-100 pt-3">
                  <span className="text-xs text-slate-400">Updated {formatDate(entry.updated_at || entry.created_at)}</span>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setViewing(entry)}
                      className="rounded px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"
                    >
                      View
                    </button>
                    {canWrite && (
                      <>
                        <button
                          type="button"
                          onClick={() => setFormState({ entry })}
                          className="rounded px-2 py-1 text-xs font-medium text-indigo-600 hover:bg-indigo-50"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => setToDelete(entry)}
                          className="rounded px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
                        >
                          Delete
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </Card>
            ))}
          </div>

          {nextCursor && (
            <div className="flex justify-center">
              <Button variant="secondary" onClick={loadMore} loading={loadingMore}>
                Load more
              </Button>
            </div>
          )}
        </>
      )}

      {viewing && !formState && (
        <EntryViewModal
          entry={viewing}
          canWrite={canWrite}
          onClose={() => setViewing(null)}
          onEdit={(entry) => setFormState({ entry })}
          onDelete={(entry) => setToDelete(entry)}
        />
      )}

      {formState && (
        <EntryFormModal
          businessId={businessId}
          businessType={businessType}
          entry={formState.entry}
          onClose={() => setFormState(null)}
          onSaved={handleSaved}
          onMissing={handleMissing}
        />
      )}

      <ConfirmDialog
        open={Boolean(toDelete)}
        title="Delete this information?"
        message={`"${toDelete?.title || ''}" will be permanently removed from this Knowledge Base.`}
        confirmLabel="Delete"
        loading={deleting}
        onConfirm={confirmDelete}
        onCancel={() => !deleting && setToDelete(null)}
      />
    </div>
  );
}
