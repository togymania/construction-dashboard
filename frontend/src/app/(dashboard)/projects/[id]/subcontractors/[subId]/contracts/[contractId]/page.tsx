"use client";

import { Fragment, useEffect, useState } from "react";
import { toast } from "sonner";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft, FileText, Wallet, CheckCircle2, Clock, AlertCircle,
  Plus, Calendar, Building2, MoreHorizontal, Pencil, Trash2,
  CheckCheck, TrendingUp, Flame, Target, Upload, Download,
  Eye, X, Bot, ShieldAlert, BarChart3,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  StatusBadge, CONTRACT_STATUS_COLORS, PAYMENT_STATUS_COLORS,
} from "@/components/ui/status-badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

import { api } from "@/lib/api-client";
import { formatRub, formatRubCompact, formatDate } from "@/lib/formatters";
import { useUser } from "@/components/providers/user-provider";
import { PaymentFormDialog } from "@/components/subcontractors/payment-form-dialog";
import { ExtractedDataPreview } from "@/components/subcontractors/extracted-data-preview";
import type {
  SubcontractorContract, SubcontractorPayment, ContractForecast,
  ContractAlert, ContractDocument as ContractDoc, DocumentType,
} from "@/types/subcontractor";

// Risk badge component
function RiskBadge({ alerts }: { alerts: ContractAlert[] }) {
  const critical = alerts.filter((a) => a.level === "critical").length;
  const warning = alerts.filter((a) => a.level === "warning").length;
  if (critical > 0) return (
    <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300 border border-red-200 dark:border-red-800">
      <ShieldAlert className="h-3 w-3" /> Critical
    </span>
  );
  if (warning > 0) return (
    <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
      <AlertCircle className="h-3 w-3" /> Warning
    </span>
  );
  return (
    <span className="inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
      <CheckCircle2 className="h-3 w-3" /> Healthy
    </span>
  );
}

export default function ContractDetailPage() {
  const params = useParams<{ id: string; subId: string; contractId: string }>();
  const projectId = parseInt(params.id, 10);
  const subId = parseInt(params.subId, 10);
  const contractId = parseInt(params.contractId, 10);
  const { user } = useUser();
  const canEdit = user && (user.role === "admin" || user.role === "project_manager");

  const [contract, setContract] = useState<SubcontractorContract | null>(null);
  const [payments, setPayments] = useState<SubcontractorPayment[] | null>(null);
  const [forecast, setForecast] = useState<ContractForecast | null>(null);
  const [alerts, setAlerts] = useState<ContractAlert[]>([]);
  const [documents, setDocuments] = useState<ContractDoc[]>([]);
  const [expandedDocId, setExpandedDocId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  function handleDocUpdated(updated: ContractDoc) {
    setDocuments((prev) => prev.map((d) => (d.id === updated.id ? updated : d)));
  }

  async function loadAll() {
    if (Number.isNaN(subId) || Number.isNaN(contractId)) return;
    setError(null);
    try {
      const [c, p, f, a, d] = await Promise.all([
        api.subcontractors.contracts.get(subId, contractId),
        api.subcontractors.payments.list(subId, contractId),
        api.subcontractors.forecast(subId, contractId).catch(() => null),
        api.subcontractors.contractAlerts(subId, contractId).catch(() => []),
        api.subcontractors.documents.list(subId, contractId).catch(() => []),
      ]);
      setContract(c);
      setPayments(p);
      setForecast(f);
      setAlerts(a);
      setDocuments(d);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    }
  }

  useEffect(() => { loadAll(); }, [subId, contractId]);

  // Payment form dialog
  const [payFormOpen, setPayFormOpen] = useState(false);
  const [editingPayment, setEditingPayment] = useState<SubcontractorPayment | null>(null);
  // Document upload
  const [uploading, setUploading] = useState(false);
  const [uploadType, setUploadType] = useState<DocumentType>("CONTRACT");
  // Preview
  const [previewDoc, setPreviewDoc] = useState<ContractDoc | null>(null);

  async function handleApprovePayment(p: SubcontractorPayment) {
    try {
      await api.subcontractors.payments.update(subId, contractId, p.id, { status: "approved" });
      toast.success(`Payment #${p.payment_number} approved`);
      await loadAll();
    } catch (err) { toast.error(err instanceof Error ? err.message : "Update failed"); }
  }

  async function handleDeletePayment(p: SubcontractorPayment) {
    if (!confirm(`Delete payment #${p.payment_number}?`)) return;
    try {
      await api.subcontractors.payments.delete(subId, contractId, p.id);
      toast.success("Payment deleted");
      await loadAll();
    } catch (err) { toast.error(err instanceof Error ? err.message : "Delete failed"); }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await api.subcontractors.documents.upload(subId, contractId, file, uploadType);
      toast.success("Document uploaded");
      await loadAll();
    } catch (err) { toast.error(err instanceof Error ? err.message : "Upload failed"); }
    setUploading(false);
    e.target.value = "";
  }

  async function handleDeleteDoc(doc: ContractDoc) {
    if (!confirm(`Delete ${doc.file_name}?`)) return;
    try {
      await api.subcontractors.documents.delete(doc.id);
      toast.success("Document deleted");
      await loadAll();
    } catch (err) { toast.error(err instanceof Error ? err.message : "Delete failed"); }
  }

  if (Number.isNaN(subId) || Number.isNaN(contractId)) {
    return <div className="p-6 text-destructive">Invalid IDs</div>;
  }
  if (contract === null) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const contractAmt = parseFloat(contract.contract_amount);
  const paidAmt = parseFloat(contract.paid_amount);
  const pendingAmt = parseFloat(contract.pending_amount);
  const remaining = contractAmt - paidAmt;
  const paidPct = contractAmt > 0 ? (paidAmt / contractAmt) * 100 : 0;
  const overPaid = paidAmt + pendingAmt > contractAmt;

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link href={`/projects/${projectId}/subcontractors/${subId}`} className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4 mr-1" /> Back to subcontractor
      </Link>
      {error && <p className="text-sm text-destructive">{error}</p>}

      {/* ── HEADER ── */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
            <div className="space-y-3 flex-1">
              <div className="flex items-center gap-3 flex-wrap">
                <FileText className="h-6 w-6 text-muted-foreground" />
                <h1 className="text-xl font-bold tracking-tight">{contract.contract_number ?? `Contract #${contract.id}`}</h1>
                <StatusBadge status={contract.status} colorMap={CONTRACT_STATUS_COLORS} />
                <RiskBadge alerts={alerts} />
              </div>
              <p className="text-sm">{contract.description}</p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm pt-2">
                {contract.subcontractor && (
                  <div className="flex items-start gap-1.5">
                    <Building2 className="h-3.5 w-3.5 mt-0.5 text-muted-foreground" />
                    <div>
                      <span className="text-muted-foreground block">Subcontractor</span>
                      <Link href={`/projects/${projectId}/subcontractors/${contract.subcontractor.id}`} className="font-medium hover:underline">{contract.subcontractor.name}</Link>
                    </div>
                  </div>
                )}
                {contract.project && (
                  <div className="flex items-start gap-1.5">
                    <Building2 className="h-3.5 w-3.5 mt-0.5 text-muted-foreground" />
                    <div>
                      <span className="text-muted-foreground block">Project</span>
                      <span className="font-medium">{contract.project.name}</span>
                    </div>
                  </div>
                )}
                <div className="flex items-start gap-1.5">
                  <Calendar className="h-3.5 w-3.5 mt-0.5 text-muted-foreground" />
                  <div>
                    <span className="text-muted-foreground block">Period</span>
                    <span className="font-medium">{formatDate(contract.start_date)} → {formatDate(contract.end_date)}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ── KPI ROW ── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <MiniKPI icon={<Wallet className="h-4 w-4" />} label="Contract Amount" value={formatRubCompact(contractAmt)} />
        <MiniKPI icon={<CheckCircle2 className="h-4 w-4 text-emerald-500" />} label="Paid" value={formatRubCompact(paidAmt)} color="text-emerald-600 dark:text-emerald-400" />
        <MiniKPI icon={<Target className="h-4 w-4" />} label="Remaining" value={formatRubCompact(remaining)} color={remaining < 0 ? "text-red-600" : ""} />
        <MiniKPI icon={<TrendingUp className="h-4 w-4" />} label="Progress" value={`${paidPct.toFixed(1)}%`} />
        <MiniKPI icon={<Flame className="h-4 w-4 text-orange-500" />} label="Burn Rate" value={forecast ? `${formatRubCompact(forecast.burn_rate_per_day)}/day` : "-"} />
      </div>

      {/* ── PROGRESS BAR ── */}
      <Card>
        <CardContent className="pt-6 space-y-4">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Payment progress</span>
            <span className="font-medium">{formatRubCompact(paidAmt)} / {formatRubCompact(contractAmt)} ({paidPct.toFixed(1)}%)</span>
          </div>
          <div className="h-3 w-full bg-muted rounded-full overflow-hidden">
            <div
              className={"h-full transition-all " + (overPaid ? "bg-red-500" : paidPct >= 100 ? "bg-emerald-500" : "bg-blue-500")}
              style={{ width: `${Math.min(100, paidPct)}%` }}
            />
          </div>
          {overPaid && (
            <p className="text-xs text-red-600 dark:text-red-400 flex items-center gap-1.5">
              <AlertCircle className="h-3.5 w-3.5" /> Total payments exceed contract amount.
            </p>
          )}
          {forecast && forecast.estimated_completion_date && (
            <p className="text-xs text-muted-foreground flex items-center gap-1.5">
              <Calendar className="h-3.5 w-3.5" />
              Projected completion: <span className="font-medium">{formatDate(forecast.estimated_completion_date)}</span>
              &nbsp;| Next 30 days: <span className="font-medium">{formatRubCompact(forecast.next_30_days_projected)}</span>
            </p>
          )}
        </CardContent>
      </Card>

      {/* ── ALERTS PANEL ── */}
      {alerts.length > 0 && (
        <Card className="border-amber-300 dark:border-amber-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 text-amber-500" /> Risk Alerts ({alerts.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {alerts.map((a, i) => (
                <div key={i} className={`flex items-start gap-2 text-sm p-2 rounded-md ${a.level === "critical" ? "bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-300" : "bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-300"}`}>
                  {a.level === "critical" ? <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" /> : <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />}
                  <span>{a.message}</span>
                  <span className="ml-auto text-xs opacity-60 shrink-0">{a.category}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── TABS: Payments | Documents ── */}
      <Tabs defaultValue="payments">
        <TabsList>
          <TabsTrigger value="payments">Payments {payments ? `(${payments.length})` : ""}</TabsTrigger>
          <TabsTrigger value="documents">Documents ({documents.length})</TabsTrigger>
        </TabsList>

        {/* Payments tab */}
        <TabsContent value="payments" className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Payments</h2>
            {canEdit && (
              <Button onClick={() => { setEditingPayment(null); setPayFormOpen(true); }}>
                <Plus className="h-4 w-4 mr-2" /> Add Payment
              </Button>
            )}
          </div>
          <Card>
            <CardContent className="pt-6">
              {payments === null ? (
                <div className="space-y-2">{[1,2,3].map(i => <Skeleton key={i} className="h-12 w-full" />)}</div>
              ) : payments.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <Wallet className="h-10 w-10 mx-auto mb-3 opacity-30" />
                  <p>No payments recorded yet.</p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12">#</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Payment Date</TableHead>
                      <TableHead>Invoice #</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                      {canEdit && <TableHead className="w-12"></TableHead>}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {payments.map((p) => (
                      <TableRow key={p.id}>
                        <TableCell className="font-mono text-xs">{p.payment_number}</TableCell>
                        <TableCell className="max-w-xs">
                          <div className="truncate" title={p.description}>{p.description}</div>
                          {p.over_payment_warning && (
                            <p className="text-[10px] text-amber-600 dark:text-amber-400 mt-0.5 flex items-center gap-1">
                              <AlertCircle className="h-2.5 w-2.5" /> {p.over_payment_warning}
                            </p>
                          )}
                        </TableCell>
                        <TableCell className="text-xs whitespace-nowrap">
                          <div>{formatDate(p.payment_date)}</div>
                          {p.due_date && <div className="text-muted-foreground">due {formatDate(p.due_date)}</div>}
                        </TableCell>
                        <TableCell className="font-mono text-xs text-muted-foreground">{p.invoice_number ?? "-"}</TableCell>
                        <TableCell><StatusBadge status={p.status} colorMap={PAYMENT_STATUS_COLORS} /></TableCell>
                        <TableCell className="text-right font-medium">{formatRub(p.amount)}</TableCell>
                        {canEdit && (
                          <TableCell>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="icon" className="h-8 w-8"><MoreHorizontal className="h-4 w-4" /></Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={() => { setEditingPayment(p); setPayFormOpen(true); }}>
                                  <Pencil className="h-4 w-4 mr-2" /> Edit
                                </DropdownMenuItem>
                                {p.status === "pending" && (
                                  <DropdownMenuItem onClick={() => handleApprovePayment(p)}>
                                    <CheckCheck className="h-4 w-4 mr-2" /> Approve
                                  </DropdownMenuItem>
                                )}
                                {p.status !== "paid" && (
                                  <DropdownMenuItem onClick={() => handleDeletePayment(p)} className="text-destructive focus:text-destructive">
                                    <Trash2 className="h-4 w-4 mr-2" /> Delete
                                  </DropdownMenuItem>
                                )}
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </TableCell>
                        )}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Documents tab */}
        <TabsContent value="documents" className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Documents</h2>
            {canEdit && (
              <div className="flex items-center gap-2">
                <Select value={uploadType} onValueChange={(v) => setUploadType(v as DocumentType)}>
                  <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="CONTRACT">Contract</SelectItem>
                    <SelectItem value="INVOICE">Invoice</SelectItem>
                    <SelectItem value="ADDENDUM">Addendum</SelectItem>
                    <SelectItem value="REPORT">Report</SelectItem>
                  </SelectContent>
                </Select>
                <Button asChild disabled={uploading}>
                  <label className="cursor-pointer">
                    <Upload className="h-4 w-4 mr-2" /> {uploading ? "Uploading..." : "Upload"}
                    <input type="file" className="hidden" onChange={handleUpload} disabled={uploading} />
                  </label>
                </Button>
              </div>
            )}
          </div>
          <Card>
            <CardContent className="pt-6">
              {documents.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <FileText className="h-10 w-10 mx-auto mb-3 opacity-30" />
                  <p>No documents uploaded yet.</p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>File Name</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Version</TableHead>
                      <TableHead>Size</TableHead>
                      <TableHead>Uploaded</TableHead>
                      <TableHead className="w-20"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {documents.map((doc) => (
                      <Fragment key={doc.id}>
                        <TableRow>
                          <TableCell className="font-medium">
                            <button
                              type="button"
                              onClick={() => setExpandedDocId(expandedDocId === doc.id ? null : doc.id)}
                              className="text-left hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors flex items-center gap-1.5"
                            >
                              {doc.extracted_data ? (
                                <Bot className="h-3.5 w-3.5 text-indigo-500 flex-shrink-0" />
                              ) : (
                                <FileText className="h-3.5 w-3.5 flex-shrink-0 opacity-50" />
                              )}
                              {doc.file_name}
                            </button>
                          </TableCell>
                          <TableCell>
                            <span className="text-xs px-2 py-0.5 rounded-full bg-muted">{doc.file_type}</span>
                          </TableCell>
                          <TableCell className="text-muted-foreground">v{doc.version}</TableCell>
                          <TableCell className="text-xs text-muted-foreground">{(doc.file_size / 1024).toFixed(1)} KB</TableCell>
                          <TableCell className="text-xs">{formatDate(doc.created_at)}</TableCell>
                          <TableCell>
                            <div className="flex gap-1">
                              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setPreviewDoc(doc)} title="Preview">
                                <Eye className="h-3.5 w-3.5" />
                              </Button>
                              <a href={api.subcontractors.documents.download(doc.id)} target="_blank" rel="noreferrer">
                                <Button variant="ghost" size="icon" className="h-7 w-7" title="Download">
                                  <Download className="h-3.5 w-3.5" />
                                </Button>
                              </a>
                              {canEdit && (
                                <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" onClick={() => handleDeleteDoc(doc)} title="Delete">
                                  <Trash2 className="h-3.5 w-3.5" />
                                </Button>
                              )}
                            </div>
                          </TableCell>
                        </TableRow>
                        {expandedDocId === doc.id && (
                          <TableRow>
                            <TableCell colSpan={6} className="bg-muted/20 p-3">
                              <ExtractedDataPreview doc={doc} canEdit={!!canEdit} onUpdated={handleDocUpdated} />
                            </TableCell>
                          </TableRow>
                        )}
                      </Fragment>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Document preview modal */}
      {previewDoc && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setPreviewDoc(null)}>
          <div className="bg-background rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="font-semibold">{previewDoc.file_name}</h3>
              <div className="flex gap-2">
                <a href={api.subcontractors.documents.download(previewDoc.id)} target="_blank" rel="noreferrer">
                  <Button variant="outline" size="sm"><Download className="h-3.5 w-3.5 mr-1" /> Download</Button>
                </a>
                <Button variant="ghost" size="icon" onClick={() => setPreviewDoc(null)}><X className="h-4 w-4" /></Button>
              </div>
            </div>
            <div className="flex-1 overflow-auto p-4">
              {previewDoc.mime_type?.includes("pdf") ? (
                <object data={api.subcontractors.documents.download(previewDoc.id)} type="application/pdf" className="w-full h-[70vh]">
                  <p>PDF preview not available. <a href={api.subcontractors.documents.download(previewDoc.id)} className="underline">Download</a></p>
                </object>
              ) : previewDoc.mime_type?.startsWith("image") ? (
                <img src={api.subcontractors.documents.download(previewDoc.id)} alt={previewDoc.file_name} className="max-w-full mx-auto rounded" />
              ) : (
                <div className="text-center py-12 text-muted-foreground">
                  <FileText className="h-12 w-12 mx-auto mb-3 opacity-30" />
                  <p>Preview not available for this file type.</p>
                  <a href={api.subcontractors.documents.download(previewDoc.id)} className="text-sm underline mt-2 block">Download file</a>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Payment dialog */}
      <PaymentFormDialog
        open={payFormOpen} onOpenChange={setPayFormOpen}
        subcontractorId={subId} contractId={contractId}
        payment={editingPayment}
        contractAmount={contractAmt}
        currentPaidPlusPending={paidAmt + pendingAmt}
        onSuccess={loadAll}
      />
    </div>
  );
}

function MiniKPI({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: string; color?: string }) {
  return (
    <Card>
      <CardContent className="pt-4 pb-3">
        <div className="flex items-center gap-2 text-muted-foreground mb-1">{icon}<span className="text-xs">{label}</span></div>
        <div className={"text-xl font-bold tracking-tight tabular-nums " + (color ?? "")}>{value}</div>
      </CardContent>
    </Card>
  );
}
