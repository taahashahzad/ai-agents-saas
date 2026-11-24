import Button from '../Button';
import Modal from '../Modal';
import { formatDateTime } from '../../utils/knowledge';

export default function EntryViewModal({ entry, canWrite, onClose, onEdit, onDelete }) {
  return (
    <Modal title={entry.title} onClose={onClose} maxWidth="max-w-xl">
      <span className="inline-flex items-center rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-medium capitalize text-indigo-700 ring-1 ring-inset ring-indigo-200">
        {entry.category}
      </span>
      <p className="mt-4 whitespace-pre-wrap break-words text-sm leading-relaxed text-slate-800">
        {entry.content}
      </p>
      <p className="mt-5 text-xs text-slate-400">
        Added {formatDateTime(entry.created_at)}
        {entry.updated_at && entry.updated_at !== entry.created_at
          ? ` · Updated ${formatDateTime(entry.updated_at)}`
          : ''}
      </p>
      <div className="mt-5 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
        {canWrite && (
          <>
            <Button variant="secondary" onClick={() => onDelete(entry)} className="!text-red-600">
              Delete
            </Button>
            <Button onClick={() => onEdit(entry)}>Edit</Button>
          </>
        )}
      </div>
    </Modal>
  );
}
