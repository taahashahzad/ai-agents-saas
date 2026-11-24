export default function Card({ children, className = '', padded = true }) {
  return (
    <div
      className={`rounded-xl border border-slate-200 bg-white shadow-sm ${padded ? 'p-6' : ''} ${className}`}
    >
      {children}
    </div>
  );
}
