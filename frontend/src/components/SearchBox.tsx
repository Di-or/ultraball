import { useState, type FormEvent } from "react";

interface SearchBoxProps {
  onSubmit: (query: string) => void;
  disabled?: boolean;
}

export function SearchBox({ onSubmit, disabled }: SearchBoxProps) {
  const [value, setValue] = useState("");

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = value.trim();
    if (trimmed) onSubmit(trimmed);
  }

  return (
    <form onSubmit={handleSubmit} className="search-box">
      <input
        type="text"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Describe what a card does…"
        aria-label="Search query"
      />
      <button type="submit" disabled={disabled || !value.trim()}>
        Search
      </button>
    </form>
  );
}
