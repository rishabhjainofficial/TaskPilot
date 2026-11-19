"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Shield, Zap, Sparkles, Database, Users, FolderGit2, ArrowLeft } from "lucide-react";
import { apiFetch } from "@/lib/api";

export default function BillingSettingsPage() {
  const queryClient = useQueryClient();
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const { data: usage, isLoading } = useQuery({
    queryKey: ["subscription-usage"],
    queryFn: () => apiFetch<any>("/billing/subscription"),
  });

  const switchPlanMutation = useMutation({
    mutationFn: (plan: string) =>
      apiFetch("/billing/switch-plan", {
        method: "POST",
        body: JSON.stringify({ plan }),
      }),
    onSuccess: (data: any) => {
      queryClient.invalidateQueries({ queryKey: ["subscription-usage"] });
      setSuccessMsg(`Successfully updated plan to ${data.plan.toUpperCase()}!`);
      setTimeout(() => setSuccessMsg(""), 4000);
    },
    onError: (err: any) => {
      setErrorMsg(err.message || "Failed to switch plan");
      setTimeout(() => setErrorMsg(""), 4000);
    },
  });

  const formatBytes = (bytes: number) => {
    if (!bytes) return "0 MB";
    const mb = bytes / (1024 * 1024);
    if (mb >= 1024) {
      return `${(mb / 1024).toFixed(1)} GB`;
    }
    return `${mb.toFixed(1)} MB`;
  };

  const getPercent = (used: number, limit: number) => {
    if (!limit) return 0;
    return Math.min(Math.round((used / limit) * 100), 100);
  };

  if (isLoading) {
    return <div className="py-12 text-center text-sm text-slate-500 animate-pulse">Loading billing settings...</div>;
  }

  const currentPlan = usage?.plan || "free";

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 pb-4">
        <div>
          <Link href="/dashboard" className="text-xs font-semibold text-blue-600 hover:underline flex items-center gap-1 mb-1">
            <ArrowLeft className="h-3 w-3" /> Back to Dashboard
          </Link>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Subscription & Quota Management</h1>
          <p className="mt-1 text-sm text-slate-500">
            Monitor per-tenant resource consumption, seat allotments, AI credits, and storage quotas
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-slate-500 uppercase">Current Tier:</span>
          <span className="rounded-lg bg-blue-100 border border-blue-200 px-3 py-1 text-xs font-bold uppercase text-blue-800">
            {currentPlan}
          </span>
        </div>
      </div>

      {/* Alerts */}
      {successMsg && (
        <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-4 text-xs font-semibold text-emerald-800">
          ✅ {successMsg}
        </div>
      )}
      {errorMsg && (
        <div className="rounded-xl bg-red-50 border border-red-200 p-4 text-xs font-semibold text-red-800">
          ⚠️ {errorMsg}
        </div>
      )}

      {/* Quota Progress Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Seats */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between text-slate-700">
            <div className="flex items-center gap-2 text-xs font-bold">
              <Users className="h-4 w-4 text-blue-600" /> Member Seats
            </div>
            <span className="text-xs font-mono font-bold text-slate-900">
              {usage?.seats_used} / {usage?.seats_limit}
            </span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
            <div
              className={`h-2 rounded-full transition-all ${
                getPercent(usage?.seats_used, usage?.seats_limit) > 85 ? "bg-amber-500" : "bg-blue-600"
              }`}
              style={{ width: `${getPercent(usage?.seats_used, usage?.seats_limit)}%` }}
            />
          </div>
          <p className="text-[11px] text-slate-400">Active member accounts in this workspace</p>
        </div>

        {/* Projects */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between text-slate-700">
            <div className="flex items-center gap-2 text-xs font-bold">
              <FolderGit2 className="h-4 w-4 text-indigo-600" /> Projects
            </div>
            <span className="text-xs font-mono font-bold text-slate-900">
              {usage?.projects_used} / {usage?.projects_limit}
            </span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
            <div
              className={`h-2 rounded-full transition-all ${
                getPercent(usage?.projects_used, usage?.projects_limit) > 85 ? "bg-amber-500" : "bg-indigo-600"
              }`}
              style={{ width: `${getPercent(usage?.projects_used, usage?.projects_limit)}%` }}
            />
          </div>
          <p className="text-[11px] text-slate-400">Active project boards created</p>
        </div>

        {/* AI Credits */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between text-slate-700">
            <div className="flex items-center gap-2 text-xs font-bold">
              <Sparkles className="h-4 w-4 text-amber-500" /> AI Credits
            </div>
            <span className="text-xs font-mono font-bold text-slate-900">
              {usage?.ai_credits_used} / {usage?.ai_credits_monthly}
            </span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
            <div
              className={`h-2 rounded-full transition-all ${
                getPercent(usage?.ai_credits_used, usage?.ai_credits_monthly) > 85 ? "bg-red-500" : "bg-amber-500"
              }`}
              style={{ width: `${getPercent(usage?.ai_credits_used, usage?.ai_credits_monthly)}%` }}
            />
          </div>
          <p className="text-[11px] text-slate-400">Monthly AI plan generation & chat actions</p>
        </div>

        {/* Storage */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between text-slate-700">
            <div className="flex items-center gap-2 text-xs font-bold">
              <Database className="h-4 w-4 text-emerald-600" /> Cloud Storage
            </div>
            <span className="text-xs font-mono font-bold text-slate-900">
              {formatBytes(usage?.storage_bytes_used)} / {formatBytes(usage?.storage_bytes_limit)}
            </span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
            <div
              className={`h-2 rounded-full transition-all ${
                getPercent(usage?.storage_bytes_used, usage?.storage_bytes_limit) > 85 ? "bg-red-500" : "bg-emerald-600"
              }`}
              style={{ width: `${getPercent(usage?.storage_bytes_used, usage?.storage_bytes_limit)}%` }}
            />
          </div>
          <p className="text-[11px] text-slate-400">S3/MinIO attachment deliverables</p>
        </div>
      </div>

      {/* Plan Selection Grid */}
      <div>
        <h2 className="text-lg font-bold text-slate-900 mb-4">Available Subscription Plans</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Free Tier */}
          <div className={`rounded-2xl border p-6 flex flex-col justify-between bg-white shadow-xs ${
            currentPlan === "free" ? "border-blue-500 ring-2 ring-blue-200" : "border-slate-200"
          }`}>
            <div>
              <div className="flex items-center justify-between">
                <h3 className="text-base font-bold text-slate-900">Free Starter</h3>
                {currentPlan === "free" && (
                  <span className="rounded bg-blue-100 px-2 py-0.5 text-[10px] font-bold uppercase text-blue-700">Current</span>
                )}
              </div>
              <p className="mt-1 text-xs text-slate-500">Perfect for small agile teams getting started</p>
              <div className="mt-4 text-2xl font-extrabold text-slate-900">$0 <span className="text-xs font-normal text-slate-500">/ month</span></div>

              <ul className="mt-5 space-y-2 text-xs text-slate-600">
                <li className="flex items-center gap-2"><Check className="h-3.5 w-3.5 text-blue-600" /> Up to 10 member seats</li>
                <li className="flex items-center gap-2"><Check className="h-3.5 w-3.5 text-blue-600" /> Up to 5 projects</li>
                <li className="flex items-center gap-2"><Check className="h-3.5 w-3.5 text-blue-600" /> 50 AI credits / month</li>
                <li className="flex items-center gap-2"><Check className="h-3.5 w-3.5 text-blue-600" /> 100 MB file storage</li>
              </ul>
            </div>

            <div className="mt-6">
              {currentPlan === "free" ? (
                <button disabled className="w-full rounded-lg bg-slate-100 py-2 text-xs font-bold text-slate-400 cursor-not-allowed">
                  Active Plan
                </button>
              ) : (
                <button
                  onClick={() => switchPlanMutation.mutate("free")}
                  disabled={switchPlanMutation.isPending}
                  className="w-full rounded-lg border border-slate-300 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50"
                >
                  Downgrade to Free
                </button>
              )}
            </div>
          </div>

          {/* Pro Tier */}
          <div className={`rounded-2xl border p-6 flex flex-col justify-between bg-white shadow-xs relative ${
            currentPlan === "pro" ? "border-blue-500 ring-2 ring-blue-200" : "border-slate-200"
          }`}>
            <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-blue-600 px-3 py-0.5 text-[10px] font-bold uppercase text-white shadow-xs">
              Recommended
            </span>
            <div>
              <div className="flex items-center justify-between">
                <h3 className="text-base font-bold text-slate-900">Pro Team</h3>
                {currentPlan === "pro" && (
                  <span className="rounded bg-blue-100 px-2 py-0.5 text-[10px] font-bold uppercase text-blue-700">Current</span>
                )}
              </div>
              <p className="mt-1 text-xs text-slate-500">For fast-moving engineering & product teams</p>
              <div className="mt-4 text-2xl font-extrabold text-slate-900">$29 <span className="text-xs font-normal text-slate-500">/ month</span></div>

              <ul className="mt-5 space-y-2 text-xs text-slate-600">
                <li className="flex items-center gap-2"><Check className="h-3.5 w-3.5 text-blue-600" /> Up to 25 member seats</li>
                <li className="flex items-center gap-2"><Check className="h-3.5 w-3.5 text-blue-600" /> Up to 20 projects</li>
                <li className="flex items-center gap-2"><Check className="h-3.5 w-3.5 text-blue-600" /> 500 AI credits / month</li>
                <li className="flex items-center gap-2"><Check className="h-3.5 w-3.5 text-blue-600" /> 10 GB file storage</li>
                <li className="flex items-center gap-2"><Check className="h-3.5 w-3.5 text-blue-600" /> Spec Document-to-Plan AI</li>
              </ul>
            </div>

            <div className="mt-6">
              {currentPlan === "pro" ? (
                <button disabled className="w-full rounded-lg bg-slate-100 py-2 text-xs font-bold text-slate-400 cursor-not-allowed">
                  Active Plan
                </button>
              ) : (
                <button
                  onClick={() => switchPlanMutation.mutate("pro")}
                  disabled={switchPlanMutation.isPending}
                  className="w-full rounded-lg bg-blue-600 py-2 text-xs font-bold text-white hover:bg-blue-700 shadow-xs"
                >
                  Upgrade to Pro
                </button>
              )}
            </div>
          </div>

          {/* Enterprise Tier */}
          <div className={`rounded-2xl border p-6 flex flex-col justify-between bg-white shadow-xs ${
            currentPlan === "enterprise" ? "border-blue-500 ring-2 ring-blue-200" : "border-slate-200"
          }`}>
            <div>
              <div className="flex items-center justify-between">
                <h3 className="text-base font-bold text-slate-900">Enterprise</h3>
                {currentPlan === "enterprise" && (
                  <span className="rounded bg-blue-100 px-2 py-0.5 text-[10px] font-bold uppercase text-blue-700">Current</span>
                )}
              </div>
              <p className="mt-1 text-xs text-slate-500">Scale across organizations with unlimited power</p>
              <div className="mt-4 text-2xl font-extrabold text-slate-900">$99 <span className="text-xs font-normal text-slate-500">/ month</span></div>

              <ul className="mt-5 space-y-2 text-xs text-slate-600">
                <li className="flex items-center gap-2"><Check className="h-3.5 w-3.5 text-blue-600" /> Up to 200 member seats</li>
                <li className="flex items-center gap-2"><Check className="h-3.5 w-3.5 text-blue-600" /> Up to 100 projects</li>
                <li className="flex items-center gap-2"><Check className="h-3.5 w-3.5 text-blue-600" /> 5,000 AI credits / month</li>
                <li className="flex items-center gap-2"><Check className="h-3.5 w-3.5 text-blue-600" /> 100 GB file storage</li>
                <li className="flex items-center gap-2"><Check className="h-3.5 w-3.5 text-blue-600" /> Dedicated SLA & Priority Support</li>
              </ul>
            </div>

            <div className="mt-6">
              {currentPlan === "enterprise" ? (
                <button disabled className="w-full rounded-lg bg-slate-100 py-2 text-xs font-bold text-slate-400 cursor-not-allowed">
                  Active Plan
                </button>
              ) : (
                <button
                  onClick={() => switchPlanMutation.mutate("enterprise")}
                  disabled={switchPlanMutation.isPending}
                  className="w-full rounded-lg bg-slate-900 py-2 text-xs font-bold text-white hover:bg-slate-800 shadow-xs"
                >
                  Upgrade to Enterprise
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
