interface Props {
  label: string;
  type: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: string;
}

export function FormField({ label, type, value, onChange, autoComplete }: Props) {
  return (
    <label className="block">
      <span className="text-sm text-muted">{label}</span>
      <input
        type={type}
        required
        autoComplete={autoComplete}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 w-full rounded border border-border bg-bg px-3 py-2 text-sm text-ink outline-none focus:border-gold"
      />
    </label>
  );
}
