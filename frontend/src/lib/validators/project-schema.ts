import { z } from "zod";

export const projectStatusSchema = z.enum([
  "planning",
  "active",
  "on_hold",
  "completed",
  "cancelled",
]);

export const projectHealthSchema = z.enum(["on_track", "at_risk", "delayed"]);

export const projectFormSchema = z
  .object({
    name: z
      .string()
      .min(1, "Name is required")
      .max(255, "Name too long"),
    description: z.string().max(5000).optional().or(z.literal("")),
    status: projectStatusSchema,
    health: projectHealthSchema,
    budget_rub: z
      .union([z.string(), z.number()])
      .transform((v) => (typeof v === "string" ? parseFloat(v) : v))
      .refine((v) => !isNaN(v) && v >= 0, "Budget must be a positive number"),
    start_date: z.string().min(1, "Start date is required"),
    end_date: z.string().min(1, "End date is required"),
    progress_pct: z
      .union([z.string(), z.number()])
      .transform((v) => (typeof v === "string" ? parseFloat(v) : v))
      .refine((v) => !isNaN(v) && v >= 0 && v <= 100, "Progress must be 0-100"),
    location: z
      .string()
      .min(1, "Location is required")
      .max(255, "Location too long"),
  })
  .refine((data) => new Date(data.end_date) >= new Date(data.start_date), {
    message: "End date must be after start date",
    path: ["end_date"],
  });

// useForm sees the raw input (string | number for numeric fields);
// after the zod transform the output type has real numbers.
export type ProjectFormInput = z.input<typeof projectFormSchema>;
export type ProjectFormOutput = z.output<typeof projectFormSchema>;
