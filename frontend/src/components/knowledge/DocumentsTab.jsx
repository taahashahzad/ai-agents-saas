import { useCallback, useEffect, useRef, useState } from 'react';
import Button from '../Button';
import ConfirmDialog from '../ConfirmDialog';
import EmptyState from '../EmptyState';
import ErrorAlert from '../ErrorAlert';
import Notice from '../Notice';
import { TableSkeleton } from '../Skeleton';
import DocumentDetailsModal from './DocumentDetailsModal';
import DocumentTable from './DocumentTable';
import UploadDropzone from './UploadDropzone';
import UploadQueue from './UploadQueue';
import {
  deleteDocument,
  downloadDocument,
  listDocuments,
  retryDocument,
  indexDocument,
  uploadDocument,
} from '../../services/documentService';
import { ACCEPT_ATTR, documentName, validateFile } from '../../utils/knowledge';
import { getErrorCode, getErrorMessage, getStatus, isCanceled } from '../../utils/errors';

/**
 * All state here belongs to ONE business (`businessId`). When the user switches
 * business the dashboard layout remounts this component, and the cleanup below
 * aborts anything still in flight, so Business A's data can never appear under B.
 */
export default function DocumentsTab({ businessId, businessName, canWrite, readOnlyReason, currentUid }) {
  const [docs, setDocs] = useState([]);
  const [nextCursor, setNextCursor] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');

  const [uploads, setUploads] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [notice, setNotice] = useState(null); // { type, text }
  const [actionError, setActionError] = useState('');

  const [details, setDetails] = useState(null);
  const [toDelete, setToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [busy, setBusy] = useState(null); // { id, kind: 'download' | 'retry' | 'index' }

  const inputRef = useRef(null);
  const uploadingRef = useRef(false); // synchronous guard against duplicate submissions
  const uploadAbortRef = useRef(null);
  const listAbortRef = useRef(null);
  const requestRef = useRef(0);

  const fetchFirstPage = useCallback(
    async ({ silent = false } = {}) => {
      listAbortRef.current?.abort();
      const controller = new AbortController();
      listAbortRef.current = controller;
      const id = ++requestRef.current;
      if (!silent) setLoading(true);
      setError('');
      try {
        const page = await listDocuments(businessId, { signal: controller.signal });
        if (id !== requestRef.current) return;
        setDocs(page.items);
        setNextCursor(page.nextCursor);
      } catch (err) {
        if (isCanceled(err) || id !== requestRef.current) return;
        if (!silent) setDocs([]);
        setError(getErrorMessage(err, 'Failed to load documents.'));
      } finally {
        if (id === requestRef.current) setLoading(false);
      }
    },
    [businessId]
  );

  useEffect(() => {
    fetchFirstPage();
    return () => {
      // Business switched or page left: cancel everything that belongs to this business.
      requestRef.current += 1;
      listAbortRef.current?.abort();
      uploadAbortRef.current?.abort();
    };
  }, [fetchFirstPage]);

  const loadMore = async () => {
    if (!nextCursor || loadingMore) return;
    const id = requestRef.current;
    setLoadingMore(true);
    try {
      const page = await listDocuments(businessId, { cursor: nextCursor, signal: listAbortRef.current?.signal });
      if (id !== requestRef.current) return;
      setDocs((prev) => [...prev, ...page.items.filter((d) => !prev.some((p) => p.document_id === d.document_id))]);
      setNextCursor(page.nextCursor);
    } catch (err) {
      if (!isCanceled(err)) setActionError(getErrorMessage(err, 'Failed to load more documents.'));
    } finally {
      setLoadingMore(false);
    }
  };

  // ---------- Upload ----------
  const handleFiles = async (fileList) => {
    if (!canWrite || uploadingRef.current) return;
    const files = Array.from(fileList || []);
    if (files.length === 0) return;

    uploadingRef.current = true;
    setUploading(true);
    setNotice(null);
    setActionError('');
    const controller = new AbortController();
    uploadAbortRef.current = controller;

    const stamp = Date.now();
    const items = files.map((file, i) => {
      const problem = validateFile(file);
      return {
        id: `${stamp}-${i}`,
        file,
        name: file.name,
        size: file.size,
        progress: 0,
        status: problem ? 'error' : 'queued',
        message: problem,
      };
    });
    setUploads(items);
    const patch = (id, changes) =>
      setUploads((prev) => prev.map((u) => (u.id === id ? { ...u, ...changes } : u)));

    let ok = 0;
    let processingFailed = 0;
    let indexingFailed = 0;
    let stopReason = '';

    for (const item of items) {
      if (item.status === 'error') continue; // failed client-side validation; never sent
      if (controller.signal.aborted) break;
      if (stopReason) {
        patch(item.id, { status: 'error', message: stopReason });
        continue;
      }
      patch(item.id, { status: 'uploading', progress: 0 });
      try {
        const doc = await uploadDocument(businessId, item.file, {
          signal: controller.signal,
          onProgress: (p) => patch(item.id, { progress: p }),
        });
        if (doc?.status === 'failed' || doc?.indexing_status === 'failed') {
          if (doc?.status === 'failed') processingFailed += 1;
          else indexingFailed += 1;
          patch(item.id, {
            status: 'warning',
            progress: 100,
            message:
              doc.status === 'failed'
                ? doc.processing_error || 'The file was saved, but its text could not be extracted.'
                : doc.indexing_error || 'The file was saved and extracted, but indexing failed.',
          });
        } else {
          ok += 1;
          patch(item.id, { status: 'done', progress: 100 });
        }
      } catch (err) {
        if (isCanceled(err)) break;
        patch(item.id, { status: 'error', message: getErrorMessage(err, 'Upload failed.') });
        const status = getStatus(err);
        if (status === 401 || status === 403 || status === 404 || getErrorCode(err) === 'business_archived') {
          stopReason = 'Skipped because an earlier upload was rejected.';
        }
      }
    }

    uploadingRef.current = false;
    uploadAbortRef.current = null;
    if (controller.signal.aborted) return; // user left this business; nothing to update

    setUploading(false);
    if (ok + processingFailed + indexingFailed > 0) {
      const parts = [];
      if (ok) parts.push(`${ok} document${ok > 1 ? 's' : ''} uploaded and text extracted`);
      if (processingFailed) {
        parts.push(`${processingFailed} uploaded but text extraction failed; use Retry in the list`);
      }
      if (indexingFailed) {
        parts.push(`${indexingFailed} uploaded and extracted, but indexing failed; use Index document in the list`);
      }
      setNotice({
        type: processingFailed || indexingFailed ? 'warning' : 'success',
        text: `${parts.join('; ')}.`,
      });
    }
    await fetchFirstPage({ silent: true });
  };

  const openPicker = () => {
    if (canWrite && !uploadingRef.current) inputRef.current?.click();
  };

  // ---------- Row actions ----------
  const handleDownload = async (doc) => {
    setBusy({ id: doc.document_id, kind: 'download' });
    setActionError('');
    try {
      await downloadDocument(businessId, doc);
    } catch (err) {
      setActionError(getErrorMessage(err, 'Failed to download the document.'));
    } finally {
      setBusy(null);
    }
  };

  const handleRetry = async (doc) => {
    setBusy({ id: doc.document_id, kind: 'retry' });
    setActionError('');
    setNotice(null);
    try {
      const updated = await retryDocument(businessId, doc.document_id);
      setDocs((prev) => prev.map((d) => (d.document_id === updated.document_id ? updated : d)));
      if (updated.status === 'failed') {
        setActionError(`Processing failed again: ${updated.processing_error || 'the text could not be extracted.'}`);
      } else {
        setNotice({ type: 'success', text: `"${documentName(updated)}" was processed successfully.` });
      }
    } catch (err) {
      setActionError(getErrorMessage(err, 'Failed to retry processing.'));
      const code = getErrorCode(err);
      if (code === 'already_processed' || code === 'already_processing' || getStatus(err) === 404) {
        await fetchFirstPage({ silent: true }); // our copy was out of date
      }
    } finally {
      setBusy(null);
    }
  };

  const handleIndex = async (doc) => {
    setBusy({ id: doc.document_id, kind: 'index' });
    setActionError('');
    setNotice(null);
    try {
      const updated = await indexDocument(businessId, doc.document_id);
      setDocs((prev) => prev.map((d) => (d.document_id === updated.document_id ? updated : d)));
      if (updated.indexing_status === 'indexed') {
        setNotice({ type: 'success', text: `"${documentName(updated)}" was indexed successfully.` });
      } else {
        setActionError(updated.indexing_error || 'Document indexing failed.');
      }
    } catch (err) {
      setActionError(getErrorMessage(err, 'Failed to index the document.'));
      await fetchFirstPage({ silent: true });
    } finally {
      setBusy(null);
    }
  };

  const confirmDelete = async () => {
    if (!toDelete) return;
    const target = toDelete;
    setDeleting(true);
    setActionError('');
    setNotice(null);
    try {
      await deleteDocument(businessId, target.document_id);
      setDocs((prev) => prev.filter((d) => d.document_id !== target.document_id));
      setNotice({ type: 'success', text: `"${documentName(target)}" was deleted.` });
    } catch (err) {
      const status = getStatus(err);
      if (status === 502) {
        // Per the contract the document is already hidden; only storage cleanup failed.
        setDocs((prev) => prev.filter((d) => d.document_id !== target.document_id));
        setNotice({
          type: 'warning',
          text: `"${documentName(target)}" was removed from your list, but storage cleanup hit a temporary error.`,
        });
      } else {
        setActionError(getErrorMessage(err, 'Failed to delete the document.'));
        if (status === 404) await fetchFirstPage({ silent: true });
      }
    } finally {
      setToDelete(null);
      setDeleting(false);
    }
  };

  const emptyAction = canWrite ? (
    <Button onClick={openPicker}>Upload document</Button>
  ) : undefined;

  return (
    <div className="space-y-5">
      {/* Hidden file input shared by the header button and the dropzone */}
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT_ATTR}
        multiple
        className="hidden"
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = ''; // allow selecting the same file again
        }}
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-slate-500">
          Files uploaded here become part of <span className="font-medium text-slate-700">{businessName}</span>&apos;s knowledge.
        </p>
        {canWrite && (
          <Button onClick={openPicker} loading={uploading} className="shrink-0">
            Upload document
          </Button>
        )}
      </div>

      {canWrite ? (
        <UploadDropzone onFiles={handleFiles} onBrowse={openPicker} disabled={uploading} busy={uploading} />
      ) : (
        readOnlyReason && <Notice type="info">{readOnlyReason}</Notice>
      )}

      <UploadQueue uploads={uploads} uploading={uploading} onClear={() => setUploads([])} />

      {notice && (
        <Notice type={notice.type} onDismiss={() => setNotice(null)}>
          {notice.text}
        </Notice>
      )}
      <ErrorAlert message={actionError} />

      {loading ? (
        <TableSkeleton />
      ) : error ? (
        <ErrorAlert message={error} onRetry={() => fetchFirstPage()} />
      ) : docs.length === 0 ? (
        <EmptyState
          title="Your Knowledge Base is empty"
          description={
            canWrite
              ? 'Upload documents or add business information to get started.'
              : 'No documents have been uploaded yet. An owner or admin can upload documents.'
          }
          action={emptyAction}
        />
      ) : (
        <>
          <DocumentTable
            documents={docs}
            currentUid={currentUid}
            canWrite={canWrite}
            busy={busy}
            onView={setDetails}
            onDownload={handleDownload}
            onRetry={handleRetry}
            onIndex={handleIndex}
            onDelete={setToDelete}
          />
          {nextCursor && (
            <div className="flex justify-center">
              <Button variant="secondary" onClick={loadMore} loading={loadingMore}>
                Load more
              </Button>
            </div>
          )}
        </>
      )}

      {details && (
        <DocumentDetailsModal
          businessId={businessId}
          doc={details}
          currentUid={currentUid}
          onClose={() => setDetails(null)}
          onDownload={handleDownload}
          downloading={busy?.kind === 'download' && busy.id === details.document_id}
        />
      )}

      <ConfirmDialog
        open={Boolean(toDelete)}
        title="Delete this document?"
        message={`"${toDelete ? documentName(toDelete) : ''}" and its extracted text will be permanently removed from this Knowledge Base.`}
        confirmLabel="Delete"
        loading={deleting}
        onConfirm={confirmDelete}
        onCancel={() => !deleting && setToDelete(null)}
      />
    </div>
  );
}
