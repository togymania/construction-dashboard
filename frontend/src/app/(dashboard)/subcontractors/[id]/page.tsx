"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft, Building2, FileText, Pencil, Phone, Mail, MapPin, Star,
  Wallet, CheckCircle2, Clock, Plus, AlertCircle, MoreHorizontal,
  Trash2, ShieldAlert, Bot, TrendingUp, BarChart3,
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
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  StatusBadge, SUBCONTRACTOR_STATUS_COLORS, CONTRACT_STATUS_COLORS,
} from "@/components/ui/status-badge";

import { api } from "@/lib/api-client";
import { formatRub, formatRubCompact, formatDate } from "@/lib/formatters";
import { useUser } from "@/components/providers/user-provider";
import { SubcontractorFormDialog } from "@/components/subcontractors/subcontractor-form-dialog";
import { ContractFormDialog } from "@/components/subcontractors/contract-form-dialog";
import type {
  Subcontractor, SubcontractorContract, RiskScore, PaymentDiscipline,
  MonthlyCashFlowPoint, SubcontractorInsights, ContractAlert,
} from "@/types/subcontractor";

// ---------- Sub-components ----------

function DisciplineBadge({ score, grade }: { score: number; grade: string }) {
  const color = score >= 85 ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800"
    : score >= 60 ? "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300 border-amber-200 dark:border-amber-800"
    : "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300 border-red-200 dark:border-red-800";
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full border ${color}`}>
      {grade} ({score})
    </span>
  );
}

function RiskLevelBadge({ level, score }: { level: string; score: number }) {
  const cfg: Record<string, { bg: string; icon: React.ReactNode }> = {
    critical: { bg: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300 border-red-200 dark:border-red-800", icon: <ShieldAlert className="h-3 w-3" /> },
    warning: { bg: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300 border-amber-200 dark:border-amber-800", icon: <AlertCircle className="h-3 w-3" /> },
    healthy: { bg: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800", icon: <CheckCircle2 className="h-3 w-3" /> },
  };
  const c = cfg[level] ?? cfg.healthy;
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2.5 py-1 rounded-full border ${c.bg}`}>
      {c.icon} {level.charAt(0).toUpperCase() + level.slice(1)} ({score})
    </span>
  );
}

// ---------- Main Page ----------

export default function SubcontractorDetailPage() {
  const params = useParams<{ id: string }>();
  const subId = parseInt(params.id, 10);
  const { user } = useUser();
  const canEdit = user && (user.role === "admin" || user.role === "project_manager");

  const [sub, setSub] = useState<Subcontractor | null>(null);
  const [contracts, setContracts] = useState<SubcontractorContract[] | null>(null);
  const [specOptions, setSpecOptions] = useState<string[]>([]);
  const [risk, setRisk] = useState<RiskScore | null>(null);
  const [discipline, setDiscipline] = useState<PaymentDiscipline | null>(null);
  const [cashflow, setCashflow] = useState<MonthlyCashFlowPoint[]>([]);
  const [insights, setInsights] = useState<SubcontractorInsights | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [editOpen, setEditOpen] = useState(false);
  const [contractFormOpen, setContractFormOpen] = useState(false);
  const [editingContract, setEditingContract] = useState<SubcontractorContract | null>(null);

  async function handleDeleteContract(c: SubcontractorContract) {
    if (!confirm(`Delete contract ${c.contract_number ?? "#" + c.id}?`)) return;
    try {
      await api.subcontractors.contracts.delete(subId, c.id);
      toast.success("Contract deleted");
      await loadAll();
    } catch (err) { toast.error(err instanceof Error ? err.message : "Delete failed"); }
  }

  async function loadAll() {
    if (Number.isNaN(subId)) return;
    setError(null);
    try {
      const [subData, contractData, specs, riskData, discData, cfData, insData] = await Promise.all([
        api.subcontractors.get(subId),
        api.subcontractors.contracts.list(subId),
        api.subcontractors.specializations(),
        api.subcontractors.riskScore(subId).catch(() => null),
        api.subcontractors.paymentDiscipline(subId).catch(() => null),
        api.subcontractors.cashflow(subId).catch(() => []),
        api.subcontractors.aiInsights(subId).catch(() => null),
      ]);
      setSub(subData); setContracts(contractData); setSpecOptions(specs);
      setRisk(riskData); setDiscipline(discData); setCashflow(cfData); setInsights(insData);
    } catch (err) { setError(err instanceof Error ? err.message : "Failed to load"); }
  }

  useEffect(() => { loadAll(); }, [subId]);

  // Cash flow chart data
  const cfChartData = useMemo(() => cashflow.map((c) => {
    const [, month] = c.month.split("-");
    const names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    return {
      month: names[parseInt(month, 10) - 1] ?? month,
      Paid: parseFloat(c.paid_amount),
      Approved: parseFloat(c.approved_amount),
      Pending: parseFloat(c.pending_amount),
    };
  }), [cashflow]);

  if (Number.isNaN(subId)) return <div className="p-6 text-destructive">Invalid subcontractor ID</div>;
  if (sub === null) return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-64" /><Skeleton className="h-32 w-full" /><Skeleton className="h-64 w-full" />
    </div>
  );

  const totalContractValue = contracts ? contracts.reduce((s, c) => s + parseFloat(c.contract_amount), 0) : 0;
  const totalPaid = contracts ? contracts.reduce((s, c) => s + parseFloat(c.paid_amount), 0) : 0;
  const totalPending = contracts ? contracts.reduce((s, c) => s + parseFloat(c.pending_amount), 0) : 0;

  return (
    <div className="space-y-6">
      <Link href="/subcontractors" className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4 mr-1" /> Back to subcontractors
      </Link>

      {/* ── HEADER ── */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
            <div className="space-y-3">
              <div className="flex items-center gap-3 flex-wrap">
                <Building2 className="h-7 w-7 text-muted-foreground" />
                <h1 className="text-2xl font-bold tracking-tight">{sub.name}</h1>
                <StatusBadge status={sub.status} colorMap={SUBCONTRACTOR_STATUS_COLORS} />
                {risk && <RiskLevelBadge level={risk.level} score={risk.score} />}
                {discipline && <DisciplineBadge score={discipline.score} grade={discipline.grade} />}
                {sub.rating && (
                  <span className="inline-flex items-center gap-1 text-sm">
                    <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" /> {sub.rating}
                  </span>
                )}
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
                {sub.tax_id && <div><span className="text-muted-foreground">Tax ID</span><div className="font-medium">{sub.tax_id}</div></div>}
                {sub.specialization && <div><span className="text-muted-foreground">Specialization</span><div className="font-medium">{sub.specialization}</div></div>}
                {sub.contact_person && <div><span className="text-muted-foreground">Contact</span><div className="font-medium">{sub.contact_person}</div></div>}
                {sub.phone && <div className="flex items-start gap-1.5"><Phone className="h-3.5 w-3.5 mt-0.5 text-muted-foreground" /><div><span className="text-muted-foreground block">Phone</span><span className="font-medium">{sub.phone}</span></div></div>}
                {sub.email && <div className="flex items-start gap-1.5 sm:col-span-2"><Mail className="h-3.5 w-3.5 mt-0.5 text-muted-foreground" /><div><span className="text-muted-foreground block">Email</span><span className="font-medium">{sub.email}</span></div></div>}
                {sub.address && <div className="flex items-start gap-1.5 sm:col-span-2 lg:col-span-4"><MapPin className="h-3.5 w-3.5 mt-0.5 text-muted-foreground" /><div><span className="text-muted-foreground block">Address</span><span className="font-medium">{sub.address}</span></div></div>}
              </div>
            </div>
            {canEdit && (
              <Button variant="outline" onClick={() => setEditOpen(true)}>
                <Pencil className="h-4 w-4 mr-2" /> Edit
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {/* ── KPI ROW ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MiniStat icon={<FileText className="h-4 w-4 text-muted-foreground" />} label="Contracts" value={contracts ? String(contracts.length) : "-"} sub={contracts ? `${contracts.filter(c => c.status === "active").length} active` : undefined} />
        <MiniStat icon={<Wallet className="h-4 w-4 text-muted-foreground" />} label="Total Value" value={formatRubCompact(totalContractValue)} />
        <MiniStat icon={<CheckCircle2 className="h-4 w-4 text-emerald-500" />} label="Paid" value={formatRubCompact(totalPaid)} color="text-emerald-600 dark:text-emerald-400" />
        <MiniStat icon={<Clock className="h-4 w-4 text-amber-500" />} label="Pending" value={formatRubCompact(totalPending)} color="text-amber-600 dark:text-amber-400" />
      </div>

      {/* ── ALERTS ── */}
      {risk && risk.alerts.length > 0 && (
        <Card className="border-amber-300 dark:border-amber-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 text-amber-500" /> Alerts ({risk.alerts.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1.5">
              {risk.alerts.slice(0, 10).map((a, i) => (
                <div key={i} className={`flex items-start gap-2 text-sm p-2 rounded-md ${a.level === "critical" ? "bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-300" : "bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-300"}`}>
                  <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                  <span>{a.message}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── TABS ── */}
      <Tabs defaultValue="contracts">
        <TabsList>
          <TabsTrigger value="contracts">Contracts {contracts ? `(${contracts.length})` : ""}</TabsTrigger>
          <TabsTrigger value="cashflow"><BarChart3 className="h-3.5 w-3.5 mr-1" />Cash Flow</TabsTrigger>
          <TabsTrigger value="insights"><Bot className="h-3.5 w-3.5 mr-1" />AI Insights</TabsTrigger>
          <TabsTrigger value="overview">Overview</TabsTrigger>
        </TabsList>

        {/* Contracts */}
        <TabsContent value="contracts" className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Contracts</h2>
            {canEdit && (
              <Button onClick={() => { setEditingContract(null); setContractFormOpen(true); }}>
                <Plus className="h-4 w-4 mr-2" /> New Contract
              </Button>
            )}
          </div>
          <Card>
            <CardContent className="pt-6">
              {contracts === null ? (
                <div className="space-y-2">{[1,2,3].map(i => <Skeleton key={i} className="h-12 w-full" />)}</div>
              ) : contracts.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <FileText className="h-10 w-10 mx-auto mb-3 opacity-30" /><p>No contracts yet.</p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Contract #</TableHead>
                      <TableHead>Project</TableHead>
                      <TableHead>Period</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                      <TableHead className="text-right">Paid</TableHead>
                      {canEdit && <TableHead className="w-12"></TableHead>}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {contracts.map((c) => {
                      const pp = parseFloat(c.contract_amount) > 0 ? (parseFloat(c.paid_amount) / parseFloat(c.contract_amount)) * 100 : 0;
                      return (
                        <TableRow key={c.id} className="cursor-pointer hover:bg-muted/40">
                          <TableCell className="font-mono text-xs">
                            <Link href={`/subcontractors/${subId}/contracts/${c.id}`} className="hover:underline">{c.contract_number ?? `#${c.id}`}</Link>
                          </TableCell>
                          <TableCell>{c.project ? <Link href={`/projects/${c.project.id}`} className="text-sm hover:underline">{c.project.name}</Link> : "-"}</TableCell>
                          <TableCell className="text-xs whitespace-nowrap">
                            <div>{formatDate(c.start_date)}</div>
                            <div className="text-muted-foreground">→ {formatDate(c.end_date)}</div>
                          </TableCell>
                          <TableCell>
                            <div className="flex flex-col gap-1 items-start">
                              <StatusBadge status={c.status} colorMap={CONTRACT_STATUS_COLORS} />
                              {c.is_overdue && <span className="inline-flex items-center gap-1 text-[10px] text-red-600 dark:text-red-400 font-medium"><AlertCircle className="h-2.5 w-2.5" />Overdue</span>}
                            </div>
                          </TableCell>
                          <TableCell className="text-right font-medium">{formatRubCompact(c.contract_amount)}</TableCell>
                          <TableCell className="text-right">
                            <div>{formatRubCompact(c.paid_amount)}</div>
                            <div className="text-xs text-muted-foreground">{pp.toFixed(0)}%</div>
                          </TableCell>
                          {canEdit && (
                            <TableCell>
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild><Button variant="ghost" size="icon" className="h-8 w-8"><MoreHorizontal className="h-4 w-4" /></Button></DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                  <DropdownMenuItem onClick={() => { setEditingContract(c); setContractFormOpen(true); }}><Pencil className="h-4 w-4 mr-2" />Edit</DropdownMenuItem>
                                  <DropdownMenuItem onClick={() => handleDeleteContract(c)} className="text-destructive focus:text-destructive"><Trash2 className="h-4 w-4 mr-2" />Delete</DropdownMenuItem>
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

        {/* Cash Flow */}
        <TabsContent value="cashflow" className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Monthly Cash Flow</CardTitle></CardHeader>
            <CardContent>
              {cfChartData.length === 0 ? (
                <div className="h-[300px] flex items-center justify-center text-sm text-muted-foreground">No payment data yet</div>
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={cfChartData}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                    <XAxis dataKey="month" className="text-xs" />
                    <YAxis tickFormatter={(v) => formatRubCompact(v)} className="text-xs" />
                    <Tooltip formatter={(v: unknown) => typeof v === "number" ? formatRubCompact(v) : String(v)} contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                    <Legend verticalAlign="top" wrapperStyle={{ fontSize: 12, paddingBottom: 8 }} />
                    <Bar dataKey="Paid" stackId="a" fill="#10b981" radius={[0,0,0,0]} />
                    <Bar dataKey="Approved" stackId="a" fill="#3b82f6" radius={[0,0,0,0]} />
                    <Bar dataKey="Pending" stackId="a" fill="#f59e0b" radius={[4,4,0,0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
          {discipline && (
            <Card>
              <CardHeader><CardTitle className="text-base">Payment Discipline</CardTitle></CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                  <div><p className="text-muted-foreground text-xs">Score</p><p className="text-2xl font-bold">{discipline.score}/100 <DisciplineBadge score={discipline.score} grade={discipline.grade} /></p></div>
                  <div><p className="text-muted-foreground text-xs">Overdue %</p><p className="font-semibold">{discipline.overdue_payment_pct}%</p></div>
                  <div><p className="text-muted-foreground text-xs">Rejected %</p><p className="font-semibold">{discipline.rejected_payment_pct}%</p></div>
                  <div><p className="text-muted-foreground text-xs">Avg Approval</p><p className="font-semibold">{discipline.avg_approval_days} days</p></div>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* AI Insights */}
        <TabsContent value="insights" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Bot className="h-4 w-4" /> AI Insights
                {insights && (
                  <span className={`text-xs px-2 py-0.5 rounded-full ml-2 ${insights.overall_health === "good" ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300" : insights.overall_health === "critical" ? "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300" : "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300"}`}>
                    {insights.overall_health}
                  </span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {!insights || insights.insights.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <Bot className="h-10 w-10 mx-auto mb-3 opacity-30" />
                  <p>No insights available yet. Add contracts and payments to generate insights.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {insights.insights.map((ins, i) => (
                    <div key={i} className={`flex items-start gap-3 p-3 rounded-lg border ${ins.severity === "critical" ? "border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-950/20" : ins.severity === "warning" ? "border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20" : "border-border bg-muted/30"}`}>
                      <div className={`mt-0.5 ${ins.severity === "critical" ? "text-red-500" : ins.severity === "warning" ? "text-amber-500" : "text-blue-500"}`}>
                        {ins.type === "prediction" ? <TrendingUp className="h-4 w-4" /> : ins.type === "alert" ? <AlertCircle className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                      </div>
                      <div className="flex-1">
                        <p className="text-sm">{ins.message}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">{ins.type}</span>
                          {ins.metric_value !== null && <span className="text-xs text-muted-foreground">metric: {ins.metric_value}</span>}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {/* AI Chat placeholder */}
              <div className="mt-6 pt-4 border-t">
                <div className="flex gap-2">
                  <input type="text" placeholder="Ask about this subcontractor..." className="flex-1 rounded-lg border px-3 py-2 text-sm bg-background" disabled />
                  <Button disabled size="sm">Ask AI</Button>
                </div>
                <p className="text-xs text-muted-foreground mt-1">AI Chat coming soon — Phase 2</p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Overview */}
        <TabsContent value="overview" className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Financial Breakdown</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-muted-foreground">Total contract value</span><span className="font-medium">{formatRub(totalContractValue)}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Total paid</span><span className="font-medium text-emerald-600 dark:text-emerald-400">{formatRub(totalPaid)}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Total pending</span><span className="font-medium text-amber-600 dark:text-amber-400">{formatRub(totalPending)}</span></div>
              <div className="flex justify-between pt-2 border-t"><span>Remaining</span><span className="font-bold">{formatRub(totalContractValue - totalPaid)}</span></div>
            </CardContent>
          </Card>
          {sub.notes && (
            <Card>
              <CardHeader><CardTitle className="text-base">Notes</CardTitle></CardHeader>
              <CardContent><p className="text-sm">{sub.notes}</p></CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      <SubcontractorFormDialog open={editOpen} onOpenChange={setEditOpen} subcontractor={sub} specializations={specOptions} onSuccess={loadAll} />
      <ContractFormDialog open={contractFormOpen} onOpenChange={setContractFormOpen} subcontractorId={subId} contract={editingContract} onSuccess={loadAll} />
    </div>
  );
}

function MiniStat({ icon, label, value, sub, color }: { icon: React.ReactNode; label: string; value: string; sub?: string; color?: string }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>{icon}
      </CardHeader>
      <CardContent>
        <div className={"text-2xl font-bold tracking-tight tabular-nums " + (color ?? "")}>{value}</div>
        {sub && <p className="text-xs mt-1 text-muted-foreground">{sub}</p>}
      </CardContent>
    </Card>
  );
}
