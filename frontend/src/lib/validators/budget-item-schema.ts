import { z } from "zod";

/**
 * Budget item form schema.
 *
 * Category resolution:
 *   - category_id    : pick an existing category (number > 0)
 *   - category_name_new : create a new category by name (1-100 chars)
 *   - exactly one must be provided
 *
 * Number coercion:
 *   - inputs from <input type="number"> arrive as strings; we accept both.
 *   - z.input<>  is what useForm sees (string | number for numeric fields).
 *   - z.output<> is what onSubmit receives after the transform runs.
 */
export const budgetItemFormSchema = z
  .object({
    category_id: z
      .union([z.string(), z.number()])
      .transform((v) => (typeof v === "string" ? parseInt(v, 10) : v))
      .nullable()
      .optional(),
    category_name_new: z
      .string()
      .min(1)
      .max(100)
      .nullable()
      .optional(),
    description: z
      .string()
      .min(1, "Description is required")
      .max(500, "Description too long"),
    planned_amount: z
      .union([z.string(), z.number()])
      .transform((v) => (typeof v === "string" ? parseFloat(v) : v))
      .refine((v) => !isNaN(v) && v >= 0, "Amount must be a positive number"),
    notes: z.string().optional().or(z.literal("")),
  })
  .refine(
    (data) => {
      const hasId = data.category_id != null && !isNaN(data.category_id) && data.category_id > 0;
      const hasName = data.category_name_new != null && data.category_name_new.length > 0;
      return hasId !== hasName; // exactly one
    },
    { message: "Category is required", path: ["category_id"] },
  );

// Input = what useForm sees (before transform)
export type BudgetItemFormInput = z.input<typeof budgetItemFormSchema>;
// Output = what onSubmit receives (after transform)
export type BudgetItemFormOutput = z.output<typeof budgetItemFormSchema>;
