"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
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
import type { Project } from "@/types/project";
import type {
  ContractPayload,
  ContractStatus,
  SubcontractorContract,
} from "@/types/subcontractor";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  subcontractorId: number;
  /** null = create, populated = edit */
  contract: SubcontractorContract | null;
  onSuccess: () => void;
}

export function ContractFormDialog({
  open,
  onOpenChange,
  subcontractorId,
  contract,
  onSuccess,
}: Props) {
  const isEdit = contract !== null;

  const [projects, setProjects] = useState<Project[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(false);

  // Form state
  const [projectId, setProjectId] = useState("");
  const [contractNumber, setContractNumber] = useState("");
  const [description, setDescription] = useState("");
  const [contractAmount, setContractAmount] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [status, setStatus] = useState<ContractStatus>("draft");
  const [scopeOfWork, setScopeOfWork] = useState("");
  const [notes, setNotes] = useState("");

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load projects when dialog opens
  useEffect(() => {
    if (!open) return;
    setLoadingProjects(true);
    api.projects
      .list()
      .then((p) => setProjects(p))
      .catch(() => setProjects([]))
      .finally(() => setLoadingProjects(false));
  }, [open]);

  // Reset form when opened
  useEffect(() => {
    if (!open) return;
    if (contract) {
      setProjectId(String(contract.project_id));
      setContractNumber(contract.contract_number ?? "");
      setDescription(contract.description);
      setContractAmount(contract.contract_amount);
      setStartDate(contract.start_date);
      setEndDate(contract.end_date);
      setStatus(contract.status);
      setScopeOfWork(contract.scope_of_work ?? "");
      setNotes(contract.notes ?? "");
    } else {
      setProjectId("");
      setContractNumber("");
      setDescription("");
      setContractAmount("");
      setStartDate("");
      setEndDate("");
      setStatus("draft");
      setScopeOfWork("");
      setNotes("");
    }
    setError(null);
  }, [open, contract]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!projectId) {
      setError("Project is required");
      return;
    }
    if (!description.trim()) {
      setError("Description is required");
      return;
    }
    if (!startDate || !endDate) {
      setError("Start and end dates are required");
      return;
    }
    if (new Date(endDate) < new Date(startDate)) {
      setError("End date must be on or after start date");
      return;
    }
    const amount = parseFloat(contractAmount);
    if (isNaN(amount) || amount < 0) {
      setError("Contract amount must be zero or positive");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const payload: ContractPayload = {
        project_id: parseInt(projectId, 10),
        contract_number: contractNumber.trim() || null,
        description: description.trim(),
        contract_amount: amount,
        start_date: startDate,
        end_date: endDate,
        status,
        scope_of_work: scopeOfWork.trim() || null,
        notes: notes.trim() || null,
      };

      if (isEdit && contract) {
        await api.subcontractors.contracts.update(
          subcontractorId,
          contract.id,
          payload
        );
      } else {
        await api.subcontractors.contracts.create(subcontractorId, payload);
      }
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Contract" : "New Contract"}</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Project (required) */}
          <div className="space-y-2">
            <Label htmlFor="ct-project">
              Project <span className="text-destructive">*</span>
            </Label>
            <Select
              value={projectId}
              onValueChange={setProjectId}
              disabled={loadingProjects}
            >
              <SelectTrigger id="ct-project">
                <SelectValue
                  placeholder={loadingProjects ? "Loading..." : "Select a project"}
                />
              </SelectTrigger>
              <SelectContent>
                {projects.map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Contract # + Status row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="ct-number">
                Contract #{" "}
                <span className="text-muted-foreground text-xs">(optional)</span>
              </Label>
              <Input
                id="ct-number"
                value={contractNumber}
                onChange={(e) => setContractNumber(e.target.value)}
                maxLength={100}
                placeholder="YE-2024-001"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ct-status">Status</Label>
              <Select
                value={status}
                onValueChange={(v) => setStatus(v as ContractStatus)}
              >
                <SelectTrigger id="ct-status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="draft">Draft</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="completed">Completed</SelectItem>
                  <SelectItem value="terminated">Terminated</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Description */}
          <div className="space-y-2">
            <Label htmlFor="ct-description">
              Description <span className="text-destructive">*</span>
            </Label>
            <Input
              id="ct-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={500}
              placeholder="Terminal B electrical infrastructure"
            />
          </div>

          {/* Amount */}
          <div className="space-y-2">
            <Label htmlFor="ct-amount">
              Contract Amount (₽) <span className="text-destructive">*</span>
            </Label>
            <Input
              id="ct-amount"
              type="number"
              step="0.01"
              min="0"
              value={contractAmount}
              onChange={(e) => setContractAmount(e.target.value)}
              placeholder="850000000"
            />
          </div>

          {/* Dates row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="ct-start">
                Start Date <span className="text-destructive">*</span>
              </Label>
              <Input
                id="ct-start"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ct-end">
                End Date <span className="text-destructive">*</span>
              </Label>
              <Input
                id="ct-end"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
          </div>

          {/* Scope of work */}
          <div className="space-y-2">
            <Label htmlFor="ct-scope">
              Scope of Work{" "}
              <span className="text-muted-foreground text-xs">(optional)</span>
            </Label>
            <Textarea
              id="ct-scope"
              value={scopeOfWork}
              onChange={(e) => setScopeOfWork(e.target.value)}
              rows={3}
              placeholder="MV/LV distribution panels, cable trays, lighting, ..."
            />
          </div>

          {/* Notes */}
          <div className="space-y-2">
            <Label htmlFor="ct-notes">
              Notes{" "}
              <span className="text-muted-foreground text-xs">(optional)</span>
            </Label>
            <Textarea
              id="ct-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
            />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? "Saving..." : isEdit ? "Update" : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
