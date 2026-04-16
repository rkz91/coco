import { Search, X } from 'lucide-react';

interface BrainSearchBarProps {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}

export function BrainSearchBar({
  value,
  onChange,
  placeholder = 'Search decisions, events, tasks...',
}: BrainSearchBarProps) {
  return (
    <div className="relative">
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label="Search brain"
        className="w-full pl-9 pr-9 py-2 bg-card border border-border rounded-lg text-sm
                   text-foreground placeholder:text-muted-foreground focus:outline-none
                   focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors"
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange('')}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Clear search"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
