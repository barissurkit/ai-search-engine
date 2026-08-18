interface SuggestionChipProps { query: string; onSelect: (query: string) => void }

export function SuggestionChip({ query, onSelect }: SuggestionChipProps) {
  return <button className="suggestion-chip" type="button" onClick={() => onSelect(query)}>{query}</button>
}
