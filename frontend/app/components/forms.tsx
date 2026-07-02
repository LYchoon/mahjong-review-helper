"use client";

export const inputCls =
  "w-full bg-stone-900 border border-stone-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500";

export function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-xs text-stone-400 mb-1">{label}</span>
      {children}
    </label>
  );
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="mb-4 bg-red-900/40 border border-red-700 text-red-200 p-3 rounded text-sm">
      {message}
    </div>
  );
}
