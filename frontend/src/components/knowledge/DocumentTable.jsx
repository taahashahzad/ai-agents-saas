import ActionMenu from '../ActionMenu';
import Card from '../Card';
import DocumentStatusBadge from './DocumentStatusBadge';
import { formatDate } from '../../utils/constants';
import { documentName, formatFileSize } from '../../utils/knowledge';

const TYPE_COLORS = {
  pdf: 'bg-red-50 text-red-600',
  docx: 'bg-blue-50 text-blue-600',
  txt: 'bg-slate-100 text-slate-600',
  csv: 'bg-emerald-50 text-emerald-600',
};

export default function DocumentTable({
  documents,
  currentUid,
  canWrite,
  busy,
  onView,
  onDownload,
  onRetry,
  onIndex,
  onDelete,
}) {
  return (
    <Card padded={false} className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">File name</th>
              <th className="hidden px-4 py-3 md:table-cell">Type</th>
              <th className="px-4 py-3">Size</th>
              <th className="hidden px-4 py-3 sm:table-cell">Uploaded</th>
              <th className="hidden px-4 py-3 lg:table-cell">Uploaded by</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {documents.map((doc) => {
              const isBusy = busy?.id === doc.document_id;
              const type = String(doc.file_type || '').toLowerCase();
              return (
                <tr key={doc.document_id} className="hover:bg-slate-50/60">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <span
                        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[10px] font-bold uppercase ${
                          TYPE_COLORS[type] || 'bg-slate-100 text-slate-600'
                        }`}
                      >
                        {type || 'file'}
                      </span>
                      <div className="min-w-0">
                        <button
                          type="button"
                          onClick={() => onView(doc)}
                          className="block max-w-[14rem] truncate text-left font-medium text-slate-900 hover:text-indigo-600 sm:max-w-xs"
                          title={documentName(doc)}
                        >
                          {documentName(doc)}
                        </button>
                        {doc.status === 'failed' && doc.processing_error && (
                          <p className="mt-0.5 max-w-[14rem] truncate text-xs text-red-600 sm:max-w-xs" title={doc.processing_error}>
                            {doc.processing_error}
                          </p>
                        )}
                        {doc.status === 'processed' && (
                          <p
                            className={`mt-0.5 text-xs ${
                              doc.indexing_status === 'failed' ? 'text-red-600' : 'text-slate-500'
                            }`}
                            title={doc.indexing_error || undefined}
                          >
                            Index: {doc.indexing_status || 'pending'}
                            {doc.indexed_chunk_count > 0 ? ` · ${doc.indexed_chunk_count} chunks` : ''}
                          </p>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="hidden whitespace-nowrap px-4 py-3 uppercase text-slate-600 md:table-cell">{type || '—'}</td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-600">{formatFileSize(doc.file_size)}</td>
                  <td className="hidden whitespace-nowrap px-4 py-3 text-slate-600 sm:table-cell">{formatDate(doc.uploaded_at)}</td>
                  <td className="hidden whitespace-nowrap px-4 py-3 text-slate-600 lg:table-cell">
                    {doc.uploaded_by ? (doc.uploaded_by === currentUid ? 'You' : 'Team member') : '—'}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <DocumentStatusBadge status={doc.status} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right">
                    {isBusy ? (
                      <span className="inline-flex items-center gap-2 text-xs text-slate-500">
                        <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-indigo-600" />
                        {busy.kind === 'download'
                          ? 'Downloading'
                          : busy.kind === 'index'
                            ? 'Indexing'
                            : 'Retrying'}
                      </span>
                    ) : (
                      <ActionMenu
                        label={`Actions for ${documentName(doc)}`}
                        disabled={Boolean(busy)}
                        items={[
                          { label: 'View details', onClick: () => onView(doc) },
                          { label: 'Download original', onClick: () => onDownload(doc) },
                          {
                            label: 'Retry processing',
                            onClick: () => onRetry(doc),
                            hidden: !(canWrite && doc.status === 'failed'),
                          },
                          {
                            label: doc.indexing_status === 'indexed' ? 'Reindex document' : 'Index document',
                            onClick: () => onIndex(doc),
                            hidden: !(canWrite && doc.status === 'processed'),
                          },
                          { label: 'Delete', onClick: () => onDelete(doc), danger: true, hidden: !canWrite },
                        ]}
                      />
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
