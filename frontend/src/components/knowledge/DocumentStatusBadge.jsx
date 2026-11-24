import { DOCUMENT_STATUS } from '../../utils/knowledge';

export default function DocumentStatusBadge({ status }) {
  const meta = DOCUMENT_STATUS[status];
  // Unknown values (should not happen per the contract) are shown as-is, neutrally.
  const style = meta?.badge || DOCUMENT_STATUS.uploaded.badge;
  const dot = meta?.dot || DOCUMENT_STATUS.uploaded.dot;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${style}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {meta?.label || String(status || 'Unknown')}
    </span>
  );
}
