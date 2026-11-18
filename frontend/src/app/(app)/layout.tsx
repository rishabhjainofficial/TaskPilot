"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiFetch, clearToken, getToken } from "@/lib/api";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
    }
  }, [router]);

  const { data: profile, isLoading } = useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<any>("/me"),
    retry: false,
  });

  const handleLogout = () => {
    clearToken();
    router.push("/login");
  };

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50">
        <div className="text-sm font-medium text-slate-500 animate-pulse">Loading workspace...</div>
      </div>
    );
  }

  const currentOrg = profile?.organizations?.find((o: any) => o.id === profile?.current_org_id) || profile?.organizations?.[0];

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Top Navbar */}
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white shadow-xs">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-6">
            <Link href="/dashboard" className="flex items-center gap-2">
              <span className="text-xl">✈️</span>
              <span className="font-bold tracking-tight text-slate-900">TaskPilot</span>
            </Link>

            {currentOrg && (
              <div className="flex items-center gap-2 rounded-lg bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                <span>🏢 {currentOrg.name}</span>
                <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-bold uppercase text-blue-700">
                  {currentOrg.role}
                </span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-4">
            <span className="text-xs text-slate-600 font-medium">{profile?.email}</span>
            <button
              onClick={handleLogout}
              className="rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">{children}</main>
    </div>
  );
}
