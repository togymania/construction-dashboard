"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { api } from "@/lib/api-client";
import {
  projectFormSchema,
  type ProjectFormInput,
} from "@/lib/validators/project-schema";
import type { Project } from "@/types/project";

interface ProjectFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  project?: Project | null;
  onSuccess: () => void;
}

export function ProjectFormDialog({
  open,
  onOpenChange,
  project,
  onSuccess,
}: ProjectFormDialogProps) {
  const isEdit = Boolean(project);

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<ProjectFormInput>({
    resolver: zodResolver(projectFormSchema),
    defaultValues: {
      name: "",
      description: "",
      status: "planning",
      health: "on_track",
      budget_usd: 0,
      budget_spent_usd: 0,
      start_date: "",
      end_date: "",
      progress_pct: 0,
      location: "",
    },
  });

  useEffect(() => {
    if (!open) return;

    if (project) {
      reset({
        name: project.name,
        description: project.description ?? "",
        status: project.status,
        health: project.health,
        budget_usd: parseFloat(project.budget_usd),
        budget_spent_usd: parseFloat(project.budget_spent_usd),
        start_date: project.start_date.slice(0, 10),
        end_date: project.end_date.slice(0, 10),
        progress_pct: parseFloat(project.progress_pct),
        location: project.location,
      });
    } else {
      reset({
        name: "",
        description: "",
        status: "planning",
        health: "on_track",
        budget_usd: 0,
        budget_spent_usd: 0,
        start_date: "",
        end_date: "",
        progress_pct: 0,
        location: "",
      });
    }
  }, [open, project, reset]);

  const statusValue = watch("status");
  const healthValue = watch("health");

  async function onSubmit(data: ProjectFormInput) {
    const payload = {
      name: data.name,
      description: data.description || null,
      status: data.status,
      health: data.health,
      budget_usd: data.budget_usd,
      budget_spent_usd: data.budget_spent_usd,
      start_date: data.start_date,
      end_date: data.end_date,
      progress_pct: data.progress_pct,
      location: data.location,
    };

    try {
      if (project) {
        await api.projects.update(project.id, payload);
      } else {
        await api.projects.create(payload);
      }
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Operation failed";
      alert(message);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[640px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Project" : "New Project"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update project details below."
              : "Create a new construction project."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input id="name" placeholder="e.g. Istanbul Metro Line 7" {...register("name")} />
            {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              placeholder="Brief project description..."
              rows={3}
              {...register("description")}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Status</Label>
              <Select value={statusValue} onValueChange={(v) => setValue("status", v as ProjectFormInput["status"])}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="planning">Planning</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="on_hold">On Hold</SelectItem>
                  <SelectItem value="completed">Completed</SelectItem>
                  <SelectItem value="cancelled">Cancelled</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Health</Label>
              <Select value={healthValue} onValueChange={(v) => setValue("health", v as ProjectFormInput["health"])}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="on_track">On track</SelectItem>
                  <SelectItem value="at_risk">At risk</SelectItem>
                  <SelectItem value="delayed">Delayed</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="budget_usd">Budget (USD)</Label>
              <Input
                id="budget_usd"
                type="number"
                step="0.01"
                min="0"
                {...register("budget_usd", { valueAsNumber: true })}
              />
              {errors.budget_usd && (
                <p className="text-xs text-destructive">{errors.budget_usd.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="budget_spent_usd">Spent (USD)</Label>
              <Input
                id="budget_spent_usd"
                type="number"
                step="0.01"
                min="0"
                {...register("budget_spent_usd", { valueAsNumber: true })}
              />
              {errors.budget_spent_usd && (
                <p className="text-xs text-destructive">
                  {errors.budget_spent_usd.message}
                </p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="start_date">Start Date</Label>
              <Input id="start_date" type="date" {...register("start_date")} />
              {errors.start_date && (
                <p className="text-xs text-destructive">{errors.start_date.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="end_date">End Date</Label>
              <Input id="end_date" type="date" {...register("end_date")} />
              {errors.end_date && (
                <p className="text-xs text-destructive">{errors.end_date.message}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="progress_pct">Progress (%)</Label>
              <Input
                id="progress_pct"
                type="number"
                step="0.1"
                min="0"
                max="100"
                {...register("progress_pct", { valueAsNumber: true })}
              />
              {errors.progress_pct && (
                <p className="text-xs text-destructive">{errors.progress_pct.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="location">Location</Label>
              <Input id="location" placeholder="Istanbul, Turkey" {...register("location")} />
              {errors.location && (
                <p className="text-xs text-destructive">{errors.location.message}</p>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEdit ? "Save changes" : "Create project"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
