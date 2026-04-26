"use client";

import { useState } from "react";
import { Check, ChevronsUpDown, Plus, Lock } from "lucide-react";
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
import { Badge } from "@/components/ui/badge";
import type { BudgetCategory } from "@/types/budget";

/**
 * Value model used by CategoryCombobox.
 *
 * - { mode: "existing", id: 5, name: "Materials" } → user picked an existing category
 * - { mode: "new",      name: "HVAC Works" }       → user wants to create a new one
 * - null                                            → nothing selected yet
 */
export type CategoryComboboxValue =
  | { mode: "existing"; id: number; name: string }
  | { mode: "new"; name: string }
  | null;

interface Props {
  categories: BudgetCategory[];
  value: CategoryComboboxValue;
  onChange: (value: CategoryComboboxValue) => void;
  disabled?: boolean;
  placeholder?: string;
  /** When true, hides system categories from the picker (rare). */
  hideSystem?: boolean;
}

export function CategoryCombobox({
  categories,
  value,
  onChange,
  disabled = false,
  placeholder = "Select or create category...",
  hideSystem = false,
}: Props) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  const visibleCategories = categories
    .filter((c) => c.is_active)
    .filter((c) => !hideSystem || !c.is_system)
    .sort((a, b) => a.display_order - b.display_order);

  // Has the typed search exactly match an existing category? (case-insensitive)
  const trimmed = search.trim();
  const exactMatch = visibleCategories.find(
    (c) => c.name.toLowerCase() === trimmed.toLowerCase()
  );

  // Show the "Create new" row only if user typed something AND no exact match.
  const showCreateOption = trimmed.length > 0 && !exactMatch;

  const triggerLabel = (() => {
    if (!value) return placeholder;
    if (value.mode === "new") return `Create "${value.name}"`;
    return value.name;
  })();

  function handleSelectExisting(cat: BudgetCategory) {
    onChange({ mode: "existing", id: cat.id, name: cat.name });
    setSearch("");
    setOpen(false);
  }

  function handleCreate() {
    if (!trimmed) return;
    onChange({ mode: "new", name: trimmed });
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
          <span className="truncate">{triggerLabel}</span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>

      <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
        <Command shouldFilter>
          <CommandInput
            placeholder="Type to search or create..."
            value={search}
            onValueChange={setSearch}
          />
          <CommandList>
            <CommandEmpty>
              {trimmed
                ? "No matching category. Type more to create one."
                : "No categories yet."}
            </CommandEmpty>

            {visibleCategories.length > 0 && (
              <CommandGroup heading="Existing">
                {visibleCategories.map((cat) => (
                  <CommandItem
                    key={cat.id}
                    value={cat.name}
                    onSelect={() => handleSelectExisting(cat)}
                  >
                    <Check
                      className={cn(
                        "mr-2 h-4 w-4",
                        value?.mode === "existing" && value.id === cat.id
                          ? "opacity-100"
                          : "opacity-0"
                      )}
                    />
                    <span className="flex-1 truncate">{cat.name}</span>
                    {cat.is_system && (
                      <Badge variant="secondary" className="ml-2 text-[10px] gap-1">
                        <Lock className="h-2.5 w-2.5" />
                        system
                      </Badge>
                    )}
                  </CommandItem>
                ))}
              </CommandGroup>
            )}

            {showCreateOption && (
              <CommandGroup heading="Create new">
                <CommandItem
                  value={`__create__${trimmed}`}
                  onSelect={handleCreate}
                  className="text-primary"
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Create &quot;{trimmed}&quot;
                </CommandItem>
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

/**
 * Helper: convert combobox value to the API payload shape
 * { category_id?: number, category_name_new?: string }
 */
export function comboboxValueToPayload(value: CategoryComboboxValue): {
  category_id: number | null;
  category_name_new: string | null;
} {
  if (!value) return { category_id: null, category_name_new: null };
  if (value.mode === "existing") return { category_id: value.id, category_name_new: null };
  return { category_id: null, category_name_new: value.name };
}

/**
 * Helper: build a CategoryComboboxValue from an existing expense/budget item
 * (which has a category object on it from the API). Used when opening edit dialogs.
 */
export function comboboxValueFromExisting(category: {
  id: number;
  name: string;
} | null): CategoryComboboxValue {
  if (!category) return null;
  return { mode: "existing", id: category.id, name: category.name };
}
