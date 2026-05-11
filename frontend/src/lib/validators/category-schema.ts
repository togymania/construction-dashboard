import { z } from "zod";

export const categoryFormSchema = z.object({
  name: z
    .string()
    .min(1, "Name is required")
    .max(100, "Name too long"),
  slug: z
    .string()
    .min(1, "Slug is required")
    .max(100, "Slug too long")
    .regex(/^[a-z0-9_-]+$/, "Slug can only contain lowercase letters, numbers, hyphens, and underscores"),
  display_order: z
    .union([z.string(), z.number()])
    .transform((v) => (typeof v === "string" ? parseInt(v, 10) : v))
    .refine((v) => !isNaN(v) && v >= 0, "Display order must be a non-negative number"),
  is_active: z.boolean(),
});

// react-hook-form needs the INPUT type (pre-transform). Use z.input so
// `display_order` can be the raw `string | number` the field produces and
// the resolver type aligns with useForm<T>.
export type CategoryFormInput = z.input<typeof categoryFormSchema>;
export type CategoryFormOutput = z.output<typeof categoryFormSchema>;
