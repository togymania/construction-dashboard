import { z } from "zod";

export const budgetItemFormSchema = z.object({
  category_id: z
    .union([z.string(), z.number()])
    .transform((v) => (typeof v === "string" ? parseInt(v, 10) : v))
    .refine((v) => !isNaN(v) && v > 0, "Category is required"),
  description: z
    .string()
    .min(1, "Description is required")
    .max(500, "Description too long"),
  planned_amount: z
    .union([z.string(), z.number()])
    .transform((v) => (typeof v === "string" ? parseFloat(v) : v))
    .refine((v) => !isNaN(v) && v >= 0, "Amount must be a positive number"),
  notes: z.string().optional().or(z.literal("")),
});

export type BudgetItemFormInput = z.infer<typeof budgetItemFormSchema>;
