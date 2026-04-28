"use client";

import { useState } from "react";
import { Check, ChevronsUpDown, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

interface Props {
  /** Pre-loaded distinct specialization values from /subcontractors/specializations */
  options: string[];
  /** Current value (null = nothing selected) */
  value: string | null;
  onChange: (value: string | null) => void;
  disabled?: boolean;
  placeholder?: string;
}

/**
 * Free-text combobox for the `specialization` field on a Subcontractor.
 *
 * Differences from CategoryCombobox:
 *   - The list is just an array of strings (no entity table behind it).
 *   - There is no "create new vs use existing" distinction at the API level —
 *     the new value is just stored as a string on the row, and the distinct
 *     endpoint will pick it up on the next list call.
 *   - We still expose a "Create" affordance for clarity, but the result is
 *     identical to picking an existing value: a plain string.
 */
export function SpecializationCombobox({
  options,
  value,
  onChange,
  disabled = false,
  placeholder = "Select or type specialization...",
}: Props) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  const trimmed = search.trim();
  const exactMatch = options.find(
    (o) => o.toLowerCase() === trimmed.toLowerCase()
  );
  const showCreateOption = trimmed.length > 0 && !exactMatch;

  function handleSelect(v: string) {
    onChange(v);
    setSearch("");
    setOpen(false);
  }

  function handleClear() {
    onChange(null);
    setSearch("");
    setOpen(false);
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          className={cn(
            "w-full justify-between font-normal",
            !value && "text-muted-foreground"
          )}
        >
          <span className="truncate">{value ?? placeholder}</span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>

      <PopoverContent
        className="w-[--radix-popover-trigger-width] p-0"
        align="start"
      >
        <Command shouldFilter>
          <CommandInput
            placeholder="Type to search or add..."
            value={search}
            onValueChange={setSearch}
          />
          <CommandList>
            <CommandEmpty>
              {trimmed
                ? "No matches. Type more to add a new value."
                : "No specializations yet."}
            </CommandEmpty>

            {options.length > 0 && (
              <CommandGroup heading="Existing">
                {options.map((opt) => (
                  <CommandItem
                    key={opt}
                    value={opt}
                    onSelect={() => handleSelect(opt)}
                  >
                    <Check
                      className={cn(
                        "mr-2 h-4 w-4",
                        value === opt ? "opacity-100" : "opacity-0"
                      )}
                    />
                    <span className="flex-1 truncate">{opt}</span>
                  </CommandItem>
                ))}
              </CommandGroup>
            )}

            {showCreateOption && (
              <CommandGroup heading="Add new">
                <CommandItem
                  value={`__create__${trimmed}`}
                  onSelect={() => handleSelect(trimmed)}
                  className="text-primary"
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Add &quot;{trimmed}&quot;
                </CommandItem>
              </CommandGroup>
            )}

            {value && (
              <CommandGroup>
                <CommandItem
                  value="__clear__"
                  onSelect={handleClear}
                  className="text-muted-foreground"
                >
                  Clear selection
                </CommandItem>
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
