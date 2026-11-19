"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Users, Shield, Award, Plus, Trash2, Edit3, X, Check, ArrowRight } from "lucide-react";
import { apiFetch } from "@/lib/api";

export default function TeamsPage() {
  const queryClient = useQueryClient();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null);

  // New Team Form State
  const [newTeamName, setNewTeamName] = useState("");
  const [newTeamDesc, setNewTeamDesc] = useState("");
  const [createError, setCreateError] = useState("");

  // Add Member Form State
  const [showAddMember, setShowAddMember] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [memberRole, setMemberRole] = useState<"member" | "lead">("member");
  const [memberJobTitle, setMemberJobTitle] = useState("");
  const [memberActionError, setMemberActionError] = useState("");

  // Editing Job Title
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [editJobTitleValue, setEditJobTitleValue] = useState("");

  // Fetch Current User & Org
  const { data: profile } = useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<any>("/me"),
  });

  // Fetch All Teams
  const { data: teams = [], isLoading: loadingTeams } = useQuery({
    queryKey: ["teams"],
    queryFn: () => apiFetch<any[]>("/teams"),
  });

  // Fetch Org Members (to select when adding to team)
  const { data: orgMembers = [] } = useQuery({
    queryKey: ["org-members"],
    queryFn: () => apiFetch<any[]>("/org/members").catch(() => []),
  });

  // Fetch Team Details for Selected Team
  const { data: selectedTeam, isLoading: loadingSelectedTeam } = useQuery({
    queryKey: ["team", selectedTeamId],
    queryFn: () => (selectedTeamId ? apiFetch<any>(`/teams/${selectedTeamId}`) : null),
    enabled: !!selectedTeamId,
  });

  // Mutations
  const createTeamMutation = useMutation({
    mutationFn: (body: { name: string; description?: string }) =>
      apiFetch("/teams", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (newTeam: any) => {
      queryClient.invalidateQueries({ queryKey: ["teams"] });
      setShowCreateModal(false);
      setNewTeamName("");
      setNewTeamDesc("");
      setCreateError("");
      setSelectedTeamId(newTeam.id);
    },
    onError: (err: any) => {
      setCreateError(err.message || "Failed to create team");
    },
  });

  const deleteTeamMutation = useMutation({
    mutationFn: (teamId: string) =>
      apiFetch(`/teams/${teamId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["teams"] });
      setSelectedTeamId(null);
    },
  });

  const addMemberMutation = useMutation({
    mutationFn: ({
      teamId,
      body,
    }: {
      teamId: string;
      body: { user_id: string; team_role: string; job_title?: string };
    }) =>
      apiFetch(`/teams/${teamId}/members`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team", selectedTeamId] });
      queryClient.invalidateQueries({ queryKey: ["teams"] });
      setShowAddMember(false);
      setSelectedUserId("");
      setMemberRole("member");
      setMemberJobTitle("");
      setMemberActionError("");
    },
    onError: (err: any) => {
      setMemberActionError(err.message || "Failed to add member");
    },
  });

  const updateMemberMutation = useMutation({
    mutationFn: ({
      teamId,
      userId,
      body,
    }: {
      teamId: string;
      userId: string;
      body: { team_role?: string; job_title?: string };
    }) =>
      apiFetch(`/teams/${teamId}/members/${userId}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team", selectedTeamId] });
      queryClient.invalidateQueries({ queryKey: ["teams"] });
      setEditingUserId(null);
      setMemberActionError("");
    },
    onError: (err: any) => {
      setMemberActionError(err.message || "Failed to update member");
    },
  });

  const removeMemberMutation = useMutation({
    mutationFn: ({ teamId, userId }: { teamId: string; userId: string }) =>
      apiFetch(`/teams/${teamId}/members/${userId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team", selectedTeamId] });
      queryClient.invalidateQueries({ queryKey: ["teams"] });
    },
    onError: (err: any) => {
      setMemberActionError(err.message || "Failed to remove member");
    },
  });

  const canManageTeams =
    profile?.current_role === "owner" ||
    profile?.current_role === "admin" ||
    profile?.current_role === "manager";

  // Filter out users already in selected team
  const availableUsersToAdd = orgMembers.filter(
    (om: any) => !selectedTeam?.members?.some((tm: any) => tm.user_id === om.user_id)
  );

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Teams & Collaboration</h1>
          <p className="mt-1 text-sm text-slate-500">
            Organize members into functional teams, assign designated Team Leads, and specify roles for AI matching
          </p>
        </div>

        {canManageTeams && (
          <button
            onClick={() => setShowCreateModal(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-xs hover:bg-blue-700 transition"
          >
            <Plus className="h-4 w-4" /> New Team
          </button>
        )}
      </div>

      {/* Teams Grid */}
      {loadingTeams ? (
        <div className="py-12 text-center text-sm text-slate-500 animate-pulse">Loading teams...</div>
      ) : teams.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center">
          <div className="text-4xl mb-3">👥</div>
          <h3 className="text-base font-semibold text-slate-900">No teams created yet</h3>
          <p className="mt-1 text-sm text-slate-500">
            Create teams to group developers, designers, and managers for projects.
          </p>
          {canManageTeams && (
            <button
              onClick={() => setShowCreateModal(true)}
              className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Create First Team
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {teams.map((team: any) => (
            <div
              key={team.id}
              onClick={() => setSelectedTeamId(team.id)}
              className="cursor-pointer group relative rounded-xl border border-slate-200 bg-white p-5 shadow-xs transition hover:border-blue-400 hover:shadow-md flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-600 font-bold">
                      <Users className="h-5 w-5" />
                    </span>
                    <div>
                      <h3 className="text-base font-semibold text-slate-900 group-hover:text-blue-600 transition">
                        {team.name}
                      </h3>
                      <span className="text-xs text-slate-400">
                        {team.members_count || 0} {team.members_count === 1 ? "member" : "members"}
                      </span>
                    </div>
                  </div>
                </div>

                {team.description && (
                  <p className="mt-3 text-xs text-slate-600 line-clamp-2">{team.description}</p>
                )}
              </div>

              <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                {team.lead ? (
                  <div className="flex items-center gap-1.5 text-xs text-slate-700">
                    <Award className="h-3.5 w-3.5 text-amber-500" />
                    <span className="font-medium text-slate-900">{team.lead.user_full_name}</span>
                    {team.lead.job_title && (
                      <span className="text-slate-400">({team.lead.job_title})</span>
                    )}
                  </div>
                ) : (
                  <span className="text-xs text-slate-400 italic">No Lead assigned</span>
                )}
                <span className="text-xs font-semibold text-blue-600 flex items-center gap-1">
                  Manage <ArrowRight className="h-3 w-3" />
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Team Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl border border-slate-100">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="text-lg font-bold text-slate-900">Create New Team</h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {createError && (
              <div className="mt-3 rounded-lg bg-red-50 p-3 text-xs text-red-600">{createError}</div>
            )}

            <form
              onSubmit={(e) => {
                e.preventDefault();
                createTeamMutation.mutate({ name: newTeamName, description: newTeamDesc });
              }}
              className="mt-4 space-y-4"
            >
              <div>
                <label className="block text-xs font-medium text-slate-700">Team Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Core Engineering, Mobile Guild"
                  value={newTeamName}
                  onChange={(e) => setNewTeamName(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700">Description</label>
                <textarea
                  rows={2}
                  placeholder="Optional team responsibilities or domain"
                  value={newTeamDesc}
                  onChange={(e) => setNewTeamDesc(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="rounded-lg border border-slate-200 px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createTeamMutation.isPending}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {createTeamMutation.isPending ? "Creating..." : "Create Team"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Team Detail / Management Modal */}
      {selectedTeamId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-2xl max-h-[90vh] flex flex-col rounded-2xl bg-white shadow-2xl border border-slate-200 overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4 bg-slate-50">
              <div>
                <div className="flex items-center gap-2">
                  <span className="flex h-7 w-7 items-center justify-center rounded-md bg-blue-100 text-blue-700 font-bold">
                    <Users className="h-4 w-4" />
                  </span>
                  <h3 className="text-lg font-bold text-slate-900">
                    {selectedTeam?.name || "Team Management"}
                  </h3>
                </div>
                {selectedTeam?.description && (
                  <p className="mt-1 text-xs text-slate-500">{selectedTeam.description}</p>
                )}
              </div>

              <div className="flex items-center gap-2">
                {canManageTeams && (
                  <button
                    onClick={() => {
                      if (confirm("Are you sure you want to delete this team?")) {
                        deleteTeamMutation.mutate(selectedTeamId);
                      }
                    }}
                    className="rounded p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50"
                    title="Delete Team"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
                <button
                  onClick={() => {
                    setSelectedTeamId(null);
                    setShowAddMember(false);
                    setMemberActionError("");
                  }}
                  className="rounded p-1.5 text-slate-400 hover:text-slate-600"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            {/* Error Message */}
            {memberActionError && (
              <div className="mx-6 mt-4 rounded-lg bg-red-50 p-3 text-xs text-red-600">
                {memberActionError}
              </div>
            )}

            {/* Content Body */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-semibold text-slate-800">
                  Members ({selectedTeam?.members?.length || 0})
                </h4>
                {canManageTeams && !showAddMember && (
                  <button
                    onClick={() => setShowAddMember(true)}
                    className="inline-flex items-center gap-1 rounded-md bg-blue-50 border border-blue-200 px-2.5 py-1 text-xs font-semibold text-blue-700 hover:bg-blue-100"
                  >
                    <Plus className="h-3 w-3" /> Add Member
                  </button>
                )}
              </div>

              {/* Add Member Form */}
              {showAddMember && (
                <div className="rounded-xl border border-blue-200 bg-blue-50/40 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-blue-900">Add Member to Team</span>
                    <button
                      onClick={() => setShowAddMember(false)}
                      className="text-slate-400 hover:text-slate-600 text-xs"
                    >
                      Cancel
                    </button>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div className="sm:col-span-1">
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                        Select User *
                      </label>
                      <select
                        value={selectedUserId}
                        onChange={(e) => setSelectedUserId(e.target.value)}
                        className="w-full rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none"
                      >
                        <option value="">Choose member...</option>
                        {availableUsersToAdd.map((u: any) => (
                          <option key={u.user_id} value={u.user_id}>
                            {u.full_name} ({u.email})
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                        Team Role
                      </label>
                      <select
                        value={memberRole}
                        onChange={(e) => setMemberRole(e.target.value as "member" | "lead")}
                        className="w-full rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none"
                      >
                        <option value="member">Member</option>
                        <option value="lead">Team Lead (Atomic)</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                        Job Title (AI Matching)
                      </label>
                      <input
                        type="text"
                        placeholder="e.g. Backend Lead"
                        value={memberJobTitle}
                        onChange={(e) => setMemberJobTitle(e.target.value)}
                        className="w-full rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-800 focus:outline-none"
                      >
                      </input>
                    </div>
                  </div>

                  {memberRole === "lead" && (
                    <p className="text-[11px] text-amber-700 bg-amber-50 p-2 rounded">
                      ⚠️ Note: Only one Team Lead can be active per team. Setting this user as Lead will atomically reassign leadership.
                    </p>
                  )}

                  <div className="flex justify-end gap-2 pt-1">
                    <button
                      onClick={() => setShowAddMember(false)}
                      className="rounded border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600"
                    >
                      Cancel
                    </button>
                    <button
                      disabled={!selectedUserId || addMemberMutation.isPending}
                      onClick={() => {
                        addMemberMutation.mutate({
                          teamId: selectedTeamId,
                          body: {
                            user_id: selectedUserId,
                            team_role: memberRole,
                            job_title: memberJobTitle.trim() || undefined,
                          },
                        });
                      }}
                      className="rounded bg-blue-600 px-3 py-1 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
                    >
                      {addMemberMutation.isPending ? "Adding..." : "Add to Team"}
                    </button>
                  </div>
                </div>
              )}

              {/* Members List */}
              {loadingSelectedTeam ? (
                <div className="py-8 text-center text-xs text-slate-400">Loading members...</div>
              ) : selectedTeam?.members?.length === 0 ? (
                <div className="rounded-lg border border-dashed border-slate-200 p-6 text-center text-xs text-slate-500">
                  No members in this team yet.
                </div>
              ) : (
                <div className="divide-y divide-slate-100 border border-slate-200 rounded-xl overflow-hidden bg-white">
                  {selectedTeam?.members?.map((m: any) => {
                    const isLead = m.team_role === "lead";
                    const isEditing = editingUserId === m.user_id;

                    return (
                      <div
                        key={m.id}
                        className={`flex items-center justify-between p-3.5 transition ${
                          isLead ? "bg-amber-50/20" : "hover:bg-slate-50/60"
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <div
                            className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold ${
                              isLead
                                ? "bg-amber-100 text-amber-800 ring-2 ring-amber-300"
                                : "bg-slate-100 text-slate-700"
                            }`}
                          >
                            {isLead ? <Award className="h-4 w-4" /> : m.user_full_name[0]?.toUpperCase()}
                          </div>

                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-bold text-slate-900">{m.user_full_name}</span>
                              <span
                                className={`rounded px-1.5 py-0.2 text-[10px] font-bold uppercase ${
                                  isLead
                                    ? "bg-amber-100 text-amber-800"
                                    : "bg-slate-100 text-slate-600"
                                }`}
                              >
                                {m.team_role}
                              </span>
                            </div>

                            {/* Job Title */}
                            {isEditing ? (
                              <div className="mt-1 flex items-center gap-1.5">
                                <input
                                  type="text"
                                  placeholder="Job Title"
                                  value={editJobTitleValue}
                                  onChange={(e) => setEditJobTitleValue(e.target.value)}
                                  className="rounded border border-slate-300 px-2 py-0.5 text-xs text-slate-800 focus:outline-none"
                                />
                                <button
                                  onClick={() => {
                                    updateMemberMutation.mutate({
                                      teamId: selectedTeamId,
                                      userId: m.user_id,
                                      body: { job_title: editJobTitleValue.trim() || undefined },
                                    });
                                  }}
                                  className="rounded bg-blue-600 p-1 text-white hover:bg-blue-700"
                                  title="Save"
                                >
                                  <Check className="h-3 w-3" />
                                </button>
                                <button
                                  onClick={() => setEditingUserId(null)}
                                  className="rounded bg-slate-200 p-1 text-slate-600 hover:bg-slate-300"
                                  title="Cancel"
                                >
                                  <X className="h-3 w-3" />
                                </button>
                              </div>
                            ) : (
                              <div className="flex items-center gap-2 text-xs text-slate-500">
                                <span>{m.user_email}</span>
                                {m.job_title && (
                                  <>
                                    <span>•</span>
                                    <span className="font-medium text-slate-700">{m.job_title}</span>
                                  </>
                                )}
                                {canManageTeams && (
                                  <button
                                    onClick={() => {
                                      setEditingUserId(m.user_id);
                                      setEditJobTitleValue(m.job_title || "");
                                    }}
                                    className="text-slate-400 hover:text-blue-600 p-0.5"
                                    title="Edit Job Title"
                                  >
                                    <Edit3 className="h-3 w-3" />
                                  </button>
                                )}
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Actions */}
                        {canManageTeams && (
                          <div className="flex items-center gap-2">
                            {!isLead ? (
                              <button
                                onClick={() => {
                                  updateMemberMutation.mutate({
                                    teamId: selectedTeamId,
                                    userId: m.user_id,
                                    body: { team_role: "lead" },
                                  });
                                }}
                                className="rounded border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] font-semibold text-amber-800 hover:bg-amber-100"
                              >
                                Make Lead
                              </button>
                            ) : (
                              <button
                                onClick={() => {
                                  updateMemberMutation.mutate({
                                    teamId: selectedTeamId,
                                    userId: m.user_id,
                                    body: { team_role: "member" },
                                  });
                                }}
                                className="rounded border border-slate-200 bg-slate-100 px-2 py-1 text-[11px] font-medium text-slate-600 hover:bg-slate-200"
                              >
                                Demote
                              </button>
                            )}

                            <button
                              onClick={() => {
                                if (confirm(`Remove ${m.user_full_name} from team?`)) {
                                  removeMemberMutation.mutate({
                                    teamId: selectedTeamId,
                                    userId: m.user_id,
                                  });
                                }
                              }}
                              className="rounded p-1 text-slate-400 hover:text-red-600 hover:bg-red-50"
                              title="Remove from Team"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="border-t border-slate-200 px-6 py-3 bg-slate-50 flex justify-end">
              <button
                onClick={() => {
                  setSelectedTeamId(null);
                  setShowAddMember(false);
                }}
                className="rounded-lg bg-slate-200 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-300"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
