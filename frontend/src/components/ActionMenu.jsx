import { useEffect, useRef, useState } from 'react';

const ITEM_HEIGHT = 38;

/**
 * "..." actions dropdown. The menu uses fixed positioning (computed from the
 * button) so it is never clipped by a table's horizontal-scroll container.
 * items: [{ label, onClick, danger?, hidden?, disabled? }]
 */
export default function ActionMenu({ items, label = 'Actions', disabled = false }) {
  const [pos, setPos] = useState(null);
  const buttonRef = useRef(null);
  const menuRef = useRef(null);
  const visible = items.filter((i) => !i.hidden);

  useEffect(() => {
    if (!pos) return undefined;
    const close = () => setPos(null);
    const onDown = (e) => {
      if (!menuRef.current?.contains(e.target) && !buttonRef.current?.contains(e.target)) close();
    };
    const onKey = (e) => e.key === 'Escape' && close();
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    window.addEventListener('resize', close);
    window.addEventListener('scroll', close, true);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('resize', close);
      window.removeEventListener('scroll', close, true);
    };
  }, [pos]);

  if (visible.length === 0) return null;

  const toggle = () => {
    if (pos) return setPos(null);
    const rect = buttonRef.current.getBoundingClientRect();
    const height = visible.length * ITEM_HEIGHT + 8;
    const opensUp = rect.bottom + height + 8 > window.innerHeight;
    setPos({
      top: opensUp ? Math.max(8, rect.top - height - 4) : rect.bottom + 4,
      right: Math.max(8, window.innerWidth - rect.right),
    });
  };

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        onClick={toggle}
        disabled={disabled}
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={Boolean(pos)}
        className="rounded-lg p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-100 disabled:cursor-not-allowed disabled:opacity-40"
      >
        <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
          <path d="M10 6a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm0 5.5a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm0 5.5a1.5 1.5 0 110-3 1.5 1.5 0 010 3z" />
        </svg>
      </button>
      {pos && (
        <div
          ref={menuRef}
          role="menu"
          style={{ position: 'fixed', top: pos.top, right: pos.right }}
          className="z-50 w-52 rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
        >
          {visible.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              disabled={item.disabled}
              onClick={() => {
                setPos(null);
                item.onClick();
              }}
              style={{ height: ITEM_HEIGHT }}
              className={`block w-full px-4 text-left text-sm disabled:opacity-40 ${
                item.danger ? 'text-red-600 hover:bg-red-50' : 'text-slate-700 hover:bg-slate-50'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </>
  );
}
