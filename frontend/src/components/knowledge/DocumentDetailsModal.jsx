import { useEffect, useState } from 'react';
import Button from '../Button';
import ErrorAlert from '../ErrorAlert';
import Modal from '../Modal';
import DocumentStatusBadge from './DocumentStatusBadge';
import { getDocument } from '../../services/documentService';
import { documentName, formatDateTime, formatFileSize } from '../../utils/knowledge';
import { getErrorMessage, isCanceled } from '../../utils/errors';

function Row({ label, children }) {
  return (
    <div className="grid grid-cols-3 gap-3 py-2.5 text-sm">
      <dt className="text-slate-500">{label}</dt>
      <dd className="col-span-2 break-words text-slate-900">{children || '—'}</dd>
    </div>
  );
}

/** Shows the list row immediately, then refreshes it from GET .../documents/{id}. */
export default function DocumentDetailsModal({ businessId, doc, currentUid, onClose, onDownload, downloading }) {
  const [current, setCurrent] = useState(doc);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        setCurrent(await getDocument(businessId, doc.document_id, { signal: controller.signal }));
      } catch (err) {
        if (!isCanceled(err)) setError(getErrorMessage(err, 'Could not refresh the document details.'));
      }
    })();
    return () => controller.abort();
  }, [businessId, doc.document_id]);

  return (
    <Modal title="Document details" description={documentName(current)} onClose={onClose}>
      <ErrorAlert message={error} className="mb-3" />
      <dl className="divide-y divide-slate-100">
        <Row label="File name">{documentName(current)}</Row>
        {current.filename && current.filename !== current.original_filename && (
          <Row label="Stored as">{current.filename}</Row>
        )}
        <Row label="Type">{String(current.file_type || '').toUpperCase()}</Row>
        <Row label="MIME type">{current.mime_type}</Row>
        <Row label="Size">{formatFileSize(current.file_size)}</Row>
        <Row label="Status">
          <DocumentStatusBadge status={current.status} />
        </Row>
        {current.status === 'failed' && (
          <Row label="Reason">
            <span className="text-red-600">{current.processing_error || 'Processing failed.'}</span>
          </Row>
        )}
        {current.status === 'processed' && (
          <Row label="Extracted text">
            {typeof current.extracted_character_count === 'number'
              ? `${current.extracted_character_count.toLocaleString()} characters`
              : '—'}
          </Row>
        )}
        <Row label="Uploaded by">
          {current.uploaded_by ? (current.uploaded_by === currentUid ? 'You' : 'Team member') : '—'}
        </Row>
        <Row label="Uploaded">{formatDateTime(current.uploaded_at)}</Row>
        <Row label="Last updated">{formatDateTime(current.updated_at)}</Row>
      </dl>
      <div className="mt-5 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
        <Button onClick={() => onDownload(current)} loading={downloading}>
          Download original
        </Button>
      </div>
    </Modal>
  );
}
