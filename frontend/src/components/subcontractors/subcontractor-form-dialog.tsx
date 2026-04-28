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
import { SpecializationCombobox } from "@/components/subcontractors/specialization-combobox";
import { api } from "@/lib/api-client";
import type {
  Subcontractor,
  SubcontractorListItem,
  SubcontractorPayload,
  SubcontractorStatus,
} from "@/types/subcontractor";

type EditTarget = Subcontractor | SubcontractorListItem | null;

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** null = create, populated = edit */
  subcontractor: EditTarget;
  /** Pre-loaded specializations list for the combobox */
  specializations: string[];
  onSuccess: () => void;
}

export function SubcontractorFormDialog({
  open,
  onOpenChange,
  subcontractor,
  specializations,
  onSuccess,
}: Props) {
  const isEdit = subcontractor !== null;

  // Form state
  const [name, setName] = useState("");
  const [taxId, setTaxId] = useState("");
  const [contactPerson, setContactPerson] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [address, setAddress] = useState("");
  const [specialization, setSpecialization] = useState<string | null>(null);
  const [status, setStatus] = useState<SubcontractorStatus>("active");
  const [rating, setRating] = useState("");
  const [notes, setNotes] = useState("");

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    if (subcontractor) {
      setName(subcontractor.name);
      setTaxId(subcontractor.tax_id ?? "");
      setSpecialization(subcontractor.specialization);
      setStatus(subcontractor.status);
      setRating(subcontractor.rating ?? "");
      // These two fields are only on Subcontractor (full), not SubcontractorListItem
      const full = subcontractor as Subcontractor;
      setContactPerson(full.contact_person ?? "");
      setPhone(full.phone ?? "");
      setEmail(full.email ?? "");
      setAddress(full.address ?? "");
      setNotes(full.notes ?? "");
    } else {
      setName("");
      setTaxId("");
      setContactPerson("");
      setPhone("");
      setEmail("");
      setAddress("");
      setSpecialization(null);
      setStatus("active");
      setRating("");
      setNotes("");
    }
    setError(null);
  }, [open, subcontractor]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setError("Name is required");
      return;
    }

    let parsedRating: number | null = null;
    if (rating.trim()) {
      const r = parseFloat(rating);
      if (isNaN(r) || r < 0 || r > 5) {
        setError("Rating must be between 0 and 5");
        return;
      }
      parsedRating = r;
    }

    setSaving(true);
    setError(null);
    try {
      const payload: SubcontractorPayload = {
        name: name.trim(),
        tax_id: taxId.trim() || null,
        contact_person: contactPerson.trim() || null,
        phone: phone.trim() || null,
        email: email.trim() || null,
        address: address.trim() || null,
        specialization: specialization,
        status,
        rating: parsedRating,
        notes: notes.trim() || null,
      };

      if (isEdit && subcontractor) {
        await api.subcontractors.update(subcontractor.id, payload);
      } else {
        await api.subcontractors.create(payload);
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
          <DialogTitle>
            {isEdit ? "Edit Subcontractor" : "New Subcontractor"}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Name (required) */}
          <div className="space-y-2">
            <Label htmlFor="sub-name">
              Company Name <span className="text-destructive">*</span>
            </Label>
            <Input
              id="sub-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={255}
              placeholder="Yilmaz Elektrik San. ve Tic. A.S."
            />
          </div>

          {/* Tax ID + Specialization row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="sub-tax-id">Tax ID / Vergi No</Label>
              <Input
                id="sub-tax-id"
                value={taxId}
                onChange={(e) => setTaxId(e.target.value)}
                maxLength={50}
                placeholder="1234567890"
              />
            </div>
            <div className="space-y-2">
              <Label>Specialization</Label>
              <SpecializationCombobox
                options={specializations}
                value={specialization}
                onChange={setSpecialization}
                placeholder="Elektrik, Beton, ..."
              />
            </div>
          </div>

          {/* Contact + Phone row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="sub-contact">Contact Person</Label>
              <Input
                id="sub-contact"
                value={contactPerson}
                onChange={(e) => setContactPerson(e.target.value)}
                maxLength={255}
                placeholder="Mehmet Yilmaz"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="sub-phone">Phone</Label>
              <Input
                id="sub-phone"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                maxLength={50}
                placeholder="+90 212 555 0101"
              />
            </div>
          </div>

          {/* Email */}
          <div className="space-y-2">
            <Label htmlFor="sub-email">Email</Label>
            <Input
              id="sub-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              maxLength={255}
              placeholder="info@firma.com.tr"
            />
          </div>

          {/* Address */}
          <div className="space-y-2">
            <Label htmlFor="sub-address">Address</Label>
            <Textarea
              id="sub-address"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              rows={2}
              placeholder="Ikitelli OSB, Istanbul"
            />
          </div>

          {/* Status + Rating row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="sub-status">Status</Label>
              <Select
                value={status}
                onValueChange={(v) => setStatus(v as SubcontractorStatus)}
              >
                <SelectTrigger id="sub-status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="suspended">Suspended</SelectItem>
                  <SelectItem value="blacklisted">Blacklisted</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="sub-rating">
                Rating (0-5){" "}
                <span className="text-muted-foreground text-xs">(optional)</span>
              </Label>
              <Input
                id="sub-rating"
                type="number"
                step="0.1"
                min="0"
                max="5"
                value={rating}
                onChange={(e) => setRating(e.target.value)}
                placeholder="4.5"
              />
            </div>
          </div>

          {/* Notes */}
          <div className="space-y-2">
            <Label htmlFor="sub-notes">
              Notes{" "}
              <span className="text-muted-foreground text-xs">(optional)</span>
            </Label>
            <Textarea
              id="sub-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder="Long-term partner, reliable on schedule."
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
