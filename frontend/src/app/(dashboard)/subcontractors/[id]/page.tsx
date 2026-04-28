"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Building2,
  FileText,
  Pencil,
  Phone,
  Mail,
  MapPin,
  Star,
  Wallet,
  CheckCircle2,
  Clock,
  Plus,
  AlertCircle,
  MoreHorizontal,
  Trash2,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  StatusBadge,
  SUBCONTRACTOR_STATUS_COLORS,
  CONTRACT_STATUS_COLORS,
} from "@/components/ui/status-badge";

import { api } from "@/lib/api-client";
import { formatRub, formatRubCompact, formatDate } from "@/lib/formatters";
import { useUser } from "@/components/providers/user-provider";
import { SubcontractorFormDialog } from "@/components/subcontractors/subcontractor-form-dialog";
import { ContractFormDialog } from "@/components/subcontractors/contract-form-dialog";
import type {
  Subcontractor,
  SubcontractorContract,
} from "@/types/subcontractor";

export default function SubcontractorDetailPage() {
  const params = useParams<{ id: string }>();
  const subId = parseInt(params.id, 10);
  const { user } = useUser();
  const canEdit =
    user && (user.role === "admin" || user.role === "project_manager");

  const [sub, setSub] = useState<Subcontractor | null>(null);
  const [contracts, setContracts] = useState<SubcontractorContract[] | null>(null);
  const [specOptions, setSpecOptions] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [editOpen, setEditOpen] = useState(false);

  // Contract form dialog state
  const [contractFormOpen, setContractFormOpen] = useState(false);
  const [editingContract, setEditingContract] = useState<SubcontractorContract | null>(null);

  function openCreateContract() {
    setEditingContract(null);
    setContractFormOpen(true);
  }

  function openEditContract(c: SubcontractorContract) {
    setEditingContract(c);
    setContractFormOpen(true);
  }

  async function handleDeleteContract(c: SubcontractorContract) {
    if (!confirm(
      `Delete contract ${c.contract_number ?? "#" + c.id}? ` +
      "Only DRAFT contracts can be deleted; the API will reject others."
    )) return;
    try {
      await api.subcontractors.contracts.delete(subId, c.id);
      await loadAll();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    }
  }

  async function loadAll() {
    if (Number.isNaN(subId)) return;
    setError(null);
    try {
      const [subData, contractData, specs] = await Promise.all([
        api.subcontractors.get(subId),
        api.subcontractors.contracts.list(subId),
        api.subcontractors.specializations(),
      ]);
      setSub(subData);
      setContracts(contractData);
      setSpecOptions(specs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    }
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subId]);

  if (Number.isNaN(subId)) {
    return <div className="p-6 text-destructive">Invalid subcontractor ID</div>;
  }

  if (sub === null) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  // Aggregates derived from contracts list
  const totalContractValue = contracts
    ? contracts.reduce((s, c) => s + parseFloat(c.contract_amount), 0)
    : 0;
  const totalPaid = contracts
    ? contracts.reduce((s, c) => s + parseFloat(c.paid_amount), 0)
    : 0;
  const totalPending = contracts
    ? contracts.reduce((s, c) => s + parseFloat(c.pending_amount), 0)
    : 0;
  const overdueCount = contracts
    ? contracts.filter((c) => c.is_overdue).length
    : 0;

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href="/subcontractors"
        className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4 mr-1" />
        Back to subcontractors
      </Link>

      {/* Header / company card */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
            <div className="space-y-3">
              <div className="flex items-center gap-3 flex-wrap">
                <Building2 className="h-7 w-7 text-muted-foreground" />
                <h1 className="text-2xl font-bold tracking-tight">{sub.name}</h1>
                <StatusBadge
                  status={sub.status}
                  colorMap={SUBCONTRACTOR_STATUS_COLORS}
                />
                {sub.rating && (
                  <span className="inline-flex items-center gap-1 text-sm">
                    <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
                    {sub.rating}
                  </span>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
                {sub.tax_id && (
                  <div>
                    <span className="text-muted-foreground">Tax ID</span>
                    <div className="font-medium">{sub.tax_id}</div>
                  </div>
                )}
                {sub.specialization && (
                  <div>
                    <span className="text-muted-foreground">Specialization</span>
                    <div className="font-medium">{sub.specialization}</div>
                  </div>
                )}
                {sub.contact_person && (
                  <div>
                    <span className="text-muted-foreground">Contact</span>
                    <div className="font-medium">{sub.contact_person}</div>
                  </div>
                )}
                {sub.phone && (
                  <div className="flex items-start gap-1.5">
                    <Phone className="h-3.5 w-3.5 mt-0.5 text-muted-foreground" />
                    <div>
                      <span className="text-muted-foreground block">Phone</span>
                      <span className="font-medium">{sub.phone}</span>
                    </div>
                  </div>
                )}
                {sub.email && (
                  <div className="flex items-start gap-1.5 sm:col-span-2">
                    <Mail className="h-3.5 w-3.5 mt-0.5 text-muted-foreground" />
                    <div>
                      <span className="text-muted-foreground block">Email</span>
                      <span className="font-medium">{sub.email}</span>
                    </div>
                  </div>
                )}
                {sub.address && (
                  <div className="flex items-start gap-1.5 sm:col-span-2 lg:col-span-4">
                    <MapPin className="h-3.5 w-3.5 mt-0.5 text-muted-foreground" />
                    <div>
                      <span className="text-muted-foreground block">Address</span>
                      <span className="font-medium">{sub.address}</span>
                    </div>
                  </div>
                )}
              </div>

              {sub.notes && (
                <div className="text-sm pt-2 border-t">
                  <span className="text-muted-foreground">Notes:</span>{" "}
                  <span>{sub.notes}</span>
                </div>
              )}
            </div>

            {canEdit && (
              <Button variant="outline" onClick={() => setEditOpen(true)}>
                <Pencil className="h-4 w-4 mr-2" />
                Edit
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {/* Tabs: Contracts | Overview */}
      <Tabs defaultValue="contracts">
        <TabsList>
          <TabsTrigger value="contracts">
            Contracts {contracts ? `(${contracts.length})` : ""}
          </TabsTrigger>
          <TabsTrigger value="overview">Overview</TabsTrigger>
        </TabsList>

        {/* Contracts tab */}
        <TabsContent value="contracts" className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Contracts</h2>
            {canEdit && (
              <Button onClick={openCreateContract}>
                <Plus className="h-4 w-4 mr-2" />
                New Contract
              </Button>
            )}
          </div>

          <Card>
            <CardContent className="pt-6">
              {contracts === null ? (
                <div className="space-y-2">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-12 w-full" />
                  ))}
                </div>
              ) : contracts.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <FileText className="h-10 w-10 mx-auto mb-3 opacity-30" />
                  <p>No contracts yet for this subcontractor.</p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Contract #</TableHead>
                      <TableHead>Project</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Period</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                      <TableHead className="text-right">Paid</TableHead>
                      {canEdit && <TableHead className="w-12"></TableHead>}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {contracts.map((c) => {
                      const paidPct =
                        parseFloat(c.contract_amount) > 0
                          ? (parseFloat(c.paid_amount) /
                              parseFloat(c.contract_amount)) *
                            100
                          : 0;
                      return (
                        <TableRow
                          key={c.id}
                          className="cursor-pointer hover:bg-muted/40"
                        >
                          <TableCell className="font-mono text-xs">
                            <Link
                              href={`/subcontractors/${subId}/contracts/${c.id}`}
                              className="hover:underline"
                            >
                              {c.contract_number ?? `#${c.id}`}
                            </Link>
                          </TableCell>
                          <TableCell>
                            {c.project ? (
                              <Link
                                href={`/projects/${c.project.id}`}
                                className="text-sm hover:underline"
                              >
                                {c.project.name}
                              </Link>
                            ) : (
                              <span className="text-muted-foreground text-sm">-</span>
                            )}
                          </TableCell>
                          <TableCell className="max-w-xs truncate" title={c.description}>
                            {c.description}
                          </TableCell>
                          <TableCell className="text-xs whitespace-nowrap">
                            <div>{formatDate(c.start_date)}</div>
                            <div className="text-muted-foreground">
                              → {formatDate(c.end_date)}
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex flex-col gap-1 items-start">
                              <StatusBadge
                                status={c.status}
                                colorMap={CONTRACT_STATUS_COLORS}
                              />
                              {c.is_overdue && (
                                <span className="inline-flex items-center gap-1 text-[10px] text-red-600 dark:text-red-400 font-medium">
                                  <AlertCircle className="h-2.5 w-2.5" />
                                  Overdue
                                </span>
                              )}
                            </div>
                          </TableCell>
                          <TableCell className="text-right font-medium">
                            {formatRubCompact(c.contract_amount)}
                          </TableCell>
                          <TableCell className="text-right">
                            <div>{formatRubCompact(c.paid_amount)}</div>
                            <div className="text-xs text-muted-foreground">
                              {paidPct.toFixed(0)}%
                            </div>
                          </TableCell>
                          {canEdit && (
                            <TableCell>
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button variant="ghost" size="icon" className="h-8 w-8">
                                    <MoreHorizontal className="h-4 w-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                  <DropdownMenuItem onClick={() => openEditContract(c)}>
                                    <Pencil className="h-4 w-4 mr-2" />
                                    Edit
                                  </DropdownMenuItem>
                                  <DropdownMenuItem
                                    onClick={() => handleDeleteContract(c)}
                                    className="text-destructive focus:text-destructive"
                                  >
                                    <Trash2 className="h-4 w-4 mr-2" />
                                    Delete
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            </TableCell>
                          )}
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Overview tab - mini KPI cards */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MiniStatCard
              icon={<FileText className="h-4 w-4 text-muted-foreground" />}
              label="Total Contracts"
              value={contracts ? String(contracts.length) : "-"}
              subline={
                contracts
                  ? `${contracts.filter((c) => c.status === "active").length} active`
                  : undefined
              }
            />
            <MiniStatCard
              icon={<Wallet className="h-4 w-4 text-muted-foreground" />}
              label="Total Contract Value"
              value={formatRubCompact(totalContractValue)}
            />
            <MiniStatCard
              icon={<CheckCircle2 className="h-4 w-4 text-muted-foreground" />}
              label="Paid"
              value={formatRubCompact(totalPaid)}
              valueColor="text-emerald-600 dark:text-emerald-400"
            />
            <MiniStatCard
              icon={<Clock className="h-4 w-4 text-muted-foreground" />}
              label="Pending"
              value={formatRubCompact(totalPending)}
              valueColor="text-amber-600 dark:text-amber-400"
            />
          </div>

          {overdueCount > 0 && (
            <Card className="border-red-300 dark:border-red-900">
              <CardContent className="pt-6 flex items-center gap-3">
                <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
                <div className="text-sm">
                  <span className="font-semibold text-red-600 dark:text-red-400">
                    {overdueCount} overdue contract{overdueCount === 1 ? "" : "s"}
                  </span>{" "}
                  <span className="text-muted-foreground">
                    (active status, end date in the past)
                  </span>
                </div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Full breakdown</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Total contract value</span>
                <span className="font-medium">{formatRub(totalContractValue)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Total paid</span>
                <span className="font-medium text-emerald-600 dark:text-emerald-400">
                  {formatRub(totalPaid)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Total pending/approved</span>
                <span className="font-medium text-amber-600 dark:text-amber-400">
                  {formatRub(totalPending)}
                </span>
              </div>
              <div className="flex justify-between pt-2 border-t">
                <span>Remaining</span>
                <span className="font-bold">
                  {formatRub(totalContractValue - totalPaid)}
                </span>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Edit subcontractor dialog */}
      <SubcontractorFormDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        subcontractor={sub}
        specializations={specOptions}
        onSuccess={loadAll}
      />

      {/* Create / Edit contract dialog */}
      <ContractFormDialog
        open={contractFormOpen}
        onOpenChange={setContractFormOpen}
        subcontractorId={subId}
        contract={editingContract}
        onSuccess={loadAll}
      />
    </div>
  );
}

interface MiniStatCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  subline?: string;
  valueColor?: string;
}

function MiniStatCard({ icon, label, value, subline, valueColor }: MiniStatCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {label}
        </CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className={"text-2xl font-bold " + (valueColor ?? "")}>{value}</div>
        {subline && (
          <p className="text-xs mt-1 text-muted-foreground">{subline}</p>
        )}
      </CardContent>
    </Card>
  );
}
