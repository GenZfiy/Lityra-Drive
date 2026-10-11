import { useEffect, useMemo, useRef, useState } from "react";
import { KeyRound, Plus, Save, ShieldCheck, UserPlus, Users } from "lucide-react";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";
import { Badge, Button, Card, Field, Input } from "../components/ui/primitives.jsx";
import { EmptyState, Loading, PageHeader } from "../components/ui/states.jsx";

const SCOPE_OPTIONS = ["platform", "college", "branch", "section", "self"];
const label = (value = "") => value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());

export default function AccessControl({ initialTab = "roles" }) {
  const { user } = useAuth();
  const permissions = new Set(user?.permissions || []);
  const canManageRoles = permissions.has("auth.role.manage") || user?.roles?.includes("super_admin");
  const canViewRoles = canManageRoles || permissions.has("auth.role.assign");
  const canManageUsers = permissions.has("auth.user.manage") || user?.roles?.includes("super_admin");
  const canViewUsers = canManageUsers || permissions.has("auth.user.view");
  const [tab, setTab] = useState(initialTab === "users" && canViewUsers ? "users" : (canViewRoles ? "roles" : "users"));
  const [roles, setRoles] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [users, setUsers] = useState([]);
  const [selectedRole, setSelectedRole] = useState(null);
  const [selectedUser, setSelectedUser] = useState(null);
  const [roleDraft, setRoleDraft] = useState(null);
  const [newUser, setNewUser] = useState({ email: "", full_name: "", password: "", role: "" });
  const [grant, setGrant] = useState({ role: "", college_id: "", branch_id: "", cohort_id: "" });
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const initialLoadStarted = useRef(false);

  async function reload(roleId = selectedRole, userId = selectedUser?.id) {
    // Keep auth-service reads sequential. Local deployments commonly use a
    // one-connection DB pool to stay within the Supabase connection budget.
    const nextRoles = canViewRoles ? await api.listRoles() : [];
    const nextCatalog = canViewRoles ? await api.listPermissions() : [];
    const nextUsers = canViewUsers ? await api.adminUsers({ q: query, limit: 200 }) : [];
    setRoles(nextRoles || []); setCatalog(nextCatalog || []); setUsers(nextUsers || []);
    if (roleId) {
      const found = (nextRoles || []).find((r) => r.id === roleId);
      if (found) { setSelectedRole(found.id); setRoleDraft({ ...found, permissions: [...found.permissions] }); }
    }
    if (userId) {
      const exists = (nextUsers || []).some((u) => u.id === userId);
      setSelectedUser(exists ? await api.adminUser(userId) : null);
    }
  }

  useEffect(() => {
    // React StrictMode replays effects in development. Avoid issuing a second
    // complete set of auth-service requests against the one-connection pool.
    if (initialLoadStarted.current) return;
    initialLoadStarted.current = true;
    reload(null, null).catch((e) => setError(e.message || "Could not load access data."))
      .finally(() => setLoading(false));
  }, []);

  const groupedPermissions = useMemo(() => catalog.reduce((result, p) => {
    (result[p.domain || "other"] ||= []).push(p);
    return result;
  }, {}), [catalog]);

  async function run(action) {
    setError(""); setBusy(true);
    try { await action(); await reload(); }
    catch (e) { setError(e.message || "The access change failed."); }
    finally { setBusy(false); }
  }

  function editRole(role) {
    setSelectedRole(role.id); setRoleDraft({ ...role, permissions: [...role.permissions] });
  }

  function startRole() {
    setTab("roles"); setSelectedRole(null);
    setRoleDraft({ name: "", description: "", scope_level: "self", permissions: [], is_active: true, is_system: false });
  }

  async function saveRole() {
    if (!roleDraft?.name?.trim()) return setError("Enter a role name.");
    await run(async () => {
      if (selectedRole) {
        await api.updateRole(selectedRole, {
          description: roleDraft.description, scope_level: roleDraft.scope_level,
          is_active: roleDraft.is_active, permissions: roleDraft.permissions,
        });
      } else {
        const saved = await api.createRole({ ...roleDraft, product: "hire" });
        setSelectedRole(saved.id);
      }
    });
  }

  async function saveUser() {
    if (!newUser.email || newUser.password.length < 8) return setError("Provide an email and a temporary password of at least 8 characters.");
    await run(async () => {
      await api.createUser({ ...newUser, product: "hire", role: newUser.role || null });
      setNewUser({ email: "", full_name: "", password: "", role: "" });
    });
  }

  async function assignSelected() {
    if (!grant.role) return setError("Choose a role to assign.");
    await run(async () => {
      await api.assignRole({ user_id: selectedUser.id, role: grant.role,
        college_id: grant.college_id || null, branch_id: grant.branch_id || null,
        cohort_id: grant.cohort_id || null });
      setGrant({ role: "", college_id: "", branch_id: "", cohort_id: "" });
    });
  }

  if (loading) return <Loading />;
  const filteredRoles = roles.filter((r) => !query || `${r.name} ${r.description || ""}`.toLowerCase().includes(query.toLowerCase()));

  return <div className="page-composition">
    <PageHeader title="Access control" subtitle="Manage Lityra Hire users, hiring roles, and the permissions behind each action." />
    {error && <div role="alert" className="mb-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</div>}
    <div className="mb-5 flex flex-wrap gap-2" role="tablist" aria-label="Access management">
      {canViewRoles && <Button variant={tab === "roles" ? "primary" : "secondary"} onClick={() => setTab("roles")}><ShieldCheck size={16} /> Roles & permissions</Button>}
      {canViewUsers && <Button variant={tab === "users" ? "primary" : "secondary"} onClick={() => setTab("users")}><Users size={16} /> Users</Button>}
    </div>

    {tab === "roles" && canViewRoles ? <>
      {canManageRoles && <div className="mb-4 flex justify-end"><Button onClick={startRole}><Plus size={16} /> Create role</Button></div>}
      <div className="grid gap-5 xl:grid-cols-[minmax(250px,0.75fr)_minmax(0,1.7fr)]">
        <Card className="overflow-hidden p-0">
          <div className="border-b border-slate-100 p-3"><Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filter Hire roles" /></div>
          <div className="max-h-[70vh] overflow-y-auto">
            {filteredRoles.map((role) => <button key={role.id} onClick={() => editRole(role)} className={`block w-full border-b border-slate-100 px-4 py-3 text-left hover:bg-slate-50 ${selectedRole === role.id ? "bg-brand-500/5" : ""}`}>
              <div className="flex items-center justify-between gap-2"><strong>{label(role.name)}</strong><Badge tone="slate">{role.scope_level}</Badge></div>
              <p className="mt-1 text-xs text-slate-500">{role.permissions.length} permissions · {role.user_count} users {role.is_system ? "· built in" : ""}</p>
            </button>)}
            {!filteredRoles.length && <EmptyState title="No roles found" />}
          </div>
        </Card>
        {roleDraft ? <Card className="p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold">{selectedRole ? label(roleDraft.name) : "New Hire role"}</h2>{!canManageRoles && <p className="mt-1 text-xs text-slate-500">Read-only role details. Permission changes require role-management access.</p>}</div>
            {canManageRoles && <Button disabled={busy} onClick={saveRole}><Save size={15} /> Save role</Button>}</div>
          <div className="mb-5 grid gap-4 sm:grid-cols-2">
            {!selectedRole && <Field label="Role name"><Input disabled={!canManageRoles} value={roleDraft.name} onChange={(e) => setRoleDraft({ ...roleDraft, name: e.target.value })} placeholder="e.g. hiring_manager" /></Field>}
            <Field label="Description"><Input disabled={!canManageRoles} value={roleDraft.description || ""} onChange={(e) => setRoleDraft({ ...roleDraft, description: e.target.value })} /></Field>
            <Field label="Data scope"><select value={roleDraft.scope_level} disabled={!canManageRoles || roleDraft.is_system} onChange={(e) => setRoleDraft({ ...roleDraft, scope_level: e.target.value })} className="h-11 w-full rounded-md border border-slate-200 bg-white px-3">{SCOPE_OPTIONS.map((s) => <option key={s}>{s}</option>)}</select></Field>
          </div>
          <div className="space-y-5 border-t border-slate-100 pt-4">
            {Object.entries(groupedPermissions).map(([domain, items]) => <section key={domain}><h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500">{domain}</h3><div className="grid gap-2 sm:grid-cols-2">
              {items.map((p) => <label key={p.code} className="flex gap-2 rounded-lg bg-slate-50 p-2 text-sm"><input type="checkbox" disabled={!canManageRoles} checked={roleDraft.permissions.includes(p.code)} onChange={() => setRoleDraft({ ...roleDraft, permissions: roleDraft.permissions.includes(p.code) ? roleDraft.permissions.filter((x) => x !== p.code) : [...roleDraft.permissions, p.code] })} /><span>{p.description}<small className="block font-mono text-[10px] text-slate-500">{p.code}</small></span></label>)}
            </div></section>)}
          </div>
        </Card> : <Card><EmptyState title="Select a role" hint="Inspect the permission map or create a custom Hire role." /></Card>}
      </div>
    </> : null}

    {tab === "users" && canViewUsers ? <div className="grid gap-5 xl:grid-cols-[minmax(280px,0.85fr)_minmax(0,1.5fr)]">
      <div className="space-y-4">
        {canManageUsers && <Card className="space-y-3 p-5"><h2 className="flex items-center gap-2 font-semibold"><UserPlus size={17} /> Create Hire user</h2>
          <Field label="Name"><Input value={newUser.full_name} onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })} /></Field>
          <Field label="Email"><Input type="email" value={newUser.email} onChange={(e) => setNewUser({ ...newUser, email: e.target.value })} /></Field>
          <Field label="Temporary password"><Input type="password" value={newUser.password} onChange={(e) => setNewUser({ ...newUser, password: e.target.value })} /></Field>
          <Field label="Initial role"><select value={newUser.role} onChange={(e) => setNewUser({ ...newUser, role: e.target.value })} className="h-11 w-full rounded-md border border-slate-200 bg-white px-3"><option value="">No role</option>{roles.filter((r) => r.is_active).map((r) => <option key={r.id} value={r.name}>{label(r.name)}</option>)}</select></Field>
          <Button disabled={busy} onClick={saveUser}><UserPlus size={15} /> Create account</Button>
        </Card>}
        <Card className="overflow-hidden p-0"><div className="border-b border-slate-100 p-3"><Input value={query} onChange={(e) => { setQuery(e.target.value); api.adminUsers({ q: e.target.value, limit: 200 }).then(setUsers).catch(() => {}); }} placeholder="Search Hire users" /></div>
          <div className="max-h-[50vh] overflow-y-auto">{users.map((u) => <button key={u.id} onClick={() => { setSelectedUser(u); api.adminUser(u.id).then(setSelectedUser).catch(() => {}); }} className={`block w-full border-b border-slate-100 px-4 py-3 text-left hover:bg-slate-50 ${selectedUser?.id === u.id ? "bg-brand-500/5" : ""}`}>
            <strong className="block truncate">{u.full_name || u.email}</strong><span className="text-xs text-slate-500">{u.email} · {u.status}</span><span className="mt-1 flex flex-wrap gap-1">{(u.roles || []).map((r) => <Badge key={r} tone="slate">{label(r)}</Badge>)}</span>
          </button>)}{!users.length && <EmptyState title="No Hire users found" />}</div>
        </Card>
      </div>
      {selectedUser ? <Card className="self-start p-5">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-lg font-semibold">{selectedUser.full_name || selectedUser.email}</h2><p className="text-sm text-slate-500">{selectedUser.email}</p></div>
          {canManageUsers && <Button variant="secondary" disabled={busy} onClick={() => run(() => api.setUserStatus(selectedUser.id, selectedUser.status === "active" ? "disabled" : "active"))}>{selectedUser.status === "active" ? "Suspend" : "Reactivate"}</Button>}</div>
        <h3 className="mb-2 mt-6 font-semibold">Role assignments</h3>
        {(selectedUser.assignments || []).map((a, i) => <div key={`${a.role}-${i}`} className="mb-2 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-100 p-3"><div><strong>{label(a.role)}</strong><p className="text-xs text-slate-500">{a.scope_level} scope{a.college_id ? ` · ${a.college_id}` : " · platform binding"}{a.branch_id ? ` · ${a.branch_id}` : ""}{a.cohort_id ? ` · ${a.cohort_id}` : ""}</p></div>{canManageUsers && <Button size="sm" variant="danger" disabled={busy} onClick={() => run(() => api.unassignRole({ user_id: selectedUser.id, role: a.role, college_id: a.college_id, branch_id: a.branch_id, cohort_id: a.cohort_id }))}>Remove</Button>}</div>)}
        {canManageUsers && <div className="mt-5 grid gap-3 border-t border-slate-100 pt-4 sm:grid-cols-2"><Field label="Assign role"><select value={grant.role} onChange={(e) => setGrant({ ...grant, role: e.target.value })} className="h-11 w-full rounded-md border border-slate-200 bg-white px-3"><option value="">Choose role</option>{roles.filter((r) => r.is_active).map((r) => <option key={r.id} value={r.name}>{label(r.name)} · {r.scope_level}</option>)}</select></Field>
          {["college_id", "branch_id", "cohort_id"].map((field) => <Field key={field} label={field.replace("_id", " ID")}><Input value={grant[field]} onChange={(e) => setGrant({ ...grant, [field]: e.target.value })} placeholder="Optional only when role scope is self" /></Field>)}
          <Button disabled={busy || !grant.role} onClick={assignSelected}><KeyRound size={15} /> Assign role</Button>
        </div>}
      </Card> : <Card><EmptyState title="Select a user" hint="Role changes are checked against your own scope and permissions." /></Card>}
    </div> : null}
  </div>;
}
