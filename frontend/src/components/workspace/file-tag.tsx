import { FileIcon, X } from "lucide-react";

interface FileTagProps {
  name: string;
  onRemove?: () => void;
}

export function FileTag({ name, onRemove }: FileTagProps) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-accent/10 text-accent text-xs font-medium">
      <FileIcon className="h-3 w-3" />
      #{name}
      {onRemove && (
        <button onClick={onRemove} className="ml-0.5 hover:text-foreground cursor-pointer" aria-label={`Remove ${name}`}>
          <X className="h-3 w-3" />
        </button>
      )}
    </span>
  );
}
