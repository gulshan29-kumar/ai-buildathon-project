'use client';

import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  AlertTriangle,
  Search,
  Filter,
  RefreshCw,
  FileText,
  Lock,
  ChevronDown,
  ChevronUp,
  Hash,
  Clock,
  User,
} from 'lucide-react';
import {
  getAllAuditEvents,
  AuditEvent,
  formatINR,
} from '../../lib/api';

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [actors, setActors] = useState<string[]>([]);
  const [integrityValid, setIntegrityValid] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchTxn, setSearchTxn] = useState('');
  const [selectedActor, setSelectedActor] = useState('ALL');
  const [expandedAuditId, setExpandedAuditId] = useState<string | null>(null);

  const fetchAuditLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getAllAuditEvents({
        transaction_id: searchTxn.trim() ? searchTxn.trim() : undefined,
        actor: selectedActor === 'ALL' ? undefined : selectedActor,
        limit: 100,
      });
      setEvents(res.events || []);
      setTotal(res.total || 0);
      setActors(res.actors || ['ORCHESTRATOR', 'POLICY_ENGINE', 'ML_MODEL', 'SIMULATOR']);
      setIntegrityValid(res.verified_integrity);
    } catch (err: any) {
      setError(err.message || 'Failed to load audit logs.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAuditLogs();
  }, [selectedActor]);

  const toggleExpand = (id: string) => {
    setExpandedAuditId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
              Platform Audit & Compliance Ledger
            </h1>
            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-500/40">
              Immutable Chain
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Tamper-evident cryptographically chained event ledger logging every ingestion, ML score, policy check, and simulator execution.
          </p>
        </div>

        {/* Verification Badge */}
        <div className="flex items-center gap-3">
          {integrityValid ? (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-950/80 border border-emerald-500/40 text-xs text-emerald-300 font-mono">
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
              <span>SHA-256 Chain Verified: 100% Intact</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-rose-950/80 border border-rose-500/40 text-xs text-rose-300 font-mono">
              <AlertTriangle className="h-4 w-4 text-rose-400" />
              <span>Audit Chain Integrity Warning</span>
            </div>
          )}

          <button
            onClick={fetchAuditLogs}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin text-indigo-400' : ''}`} />
            <span>Verify & Refresh</span>
          </button>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="rounded-xl border border-fintech-border bg-fintech-card/80 p-4 shadow-fintech-card glass-panel flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="relative w-full md:w-80">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search by Transaction ID..."
            value={searchTxn}
            onChange={(e) => setSearchTxn(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && fetchAuditLogs()}
            className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div className="flex items-center gap-2 w-full md:w-auto">
          <span className="text-xs text-slate-400 flex items-center gap-1">
            <Filter className="h-3 w-3" /> Actor:
          </span>
          <select
            value={selectedActor}
            onChange={(e) => setSelectedActor(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-indigo-500"
          >
            <option value="ALL">All Actors</option>
            {actors.map((act) => (
              <option key={act} value={act}>
                {act}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Audit Logs Table */}
      <div className="rounded-xl border border-fintech-border bg-fintech-card/80 shadow-fintech-card glass-panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 text-slate-400 uppercase tracking-wider text-[11px] bg-slate-900/60 font-semibold">
              <tr>
                <th className="py-3 px-4">Audit ID</th>
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4">Event Type</th>
                <th className="py-3 px-4">Actor</th>
                <th className="py-3 px-4">Transaction ID</th>
                <th className="py-3 px-4">Cryptographic Hash</th>
                <th className="py-3 px-4 text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-medium font-mono">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400 font-sans">
                    <RefreshCw className="h-6 w-6 animate-spin mx-auto text-indigo-400 mb-2" />
                    Loading audit trail from tamper-evident ledger...
                  </td>
                </tr>
              ) : events.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500 font-sans">
                    No audit records match the current filter.
                  </td>
                </tr>
              ) : (
                events.map((evt) => {
                  const isExpanded = expandedAuditId === evt.audit_id;

                  return (
                    <React.Fragment key={evt.audit_id}>
                      <tr
                        onClick={() => toggleExpand(evt.audit_id)}
                        className="hover:bg-slate-800/40 cursor-pointer transition"
                      >
                        {/* Audit ID */}
                        <td className="py-3 px-4 text-slate-400">
                          {evt.audit_id}
                        </td>

                        {/* Timestamp */}
                        <td className="py-3 px-4 text-slate-300 font-sans text-[11px]">
                          {new Date(evt.timestamp).toLocaleString()}
                        </td>

                        {/* Event Type */}
                        <td className="py-3 px-4 text-white font-semibold">
                          {evt.event_type}
                        </td>

                        {/* Actor */}
                        <td className="py-3 px-4">
                          <span className="px-2 py-0.5 rounded text-[10px] bg-indigo-950/80 text-indigo-300 border border-indigo-500/30">
                            {evt.actor}
                          </span>
                        </td>

                        {/* Transaction ID */}
                        <td className="py-3 px-4 text-slate-300">
                          {evt.transaction_id}
                        </td>

                        {/* Cryptographic Hash */}
                        <td className="py-3 px-4 text-slate-500 text-[11px] truncate max-w-[140px]">
                          {evt.hash}
                        </td>

                        {/* Expand Button */}
                        <td className="py-3 px-4 text-right font-sans">
                          <button className="text-slate-400 hover:text-white">
                            {isExpanded ? (
                              <ChevronUp className="h-4 w-4 inline" />
                            ) : (
                              <ChevronDown className="h-4 w-4 inline" />
                            )}
                          </button>
                        </td>
                      </tr>

                      {/* Expandable JSON Detail Row */}
                      {isExpanded && (
                        <tr className="bg-slate-950/80 border-b border-slate-800">
                          <td colSpan={7} className="p-4 font-mono text-xs">
                            <div className="space-y-2">
                              <div className="flex items-center justify-between text-[11px] text-slate-400">
                                <span>Full Event Metadata & Tamper Verification Chain:</span>
                                <span>Previous Hash: {evt.previous_hash || 'GENESIS'}</span>
                              </div>
                              <pre className="p-3 bg-slate-900 border border-slate-800 rounded-lg text-slate-300 text-[11px] overflow-x-auto">
                                {JSON.stringify(evt, null, 2)}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800 bg-slate-900/40 text-xs text-slate-400 font-mono">
          <span>Showing {events.length} of {total} verified audit logs</span>
          <span className="flex items-center gap-1.5 text-emerald-400">
            <Lock className="h-3 w-3" /> Cryptographic Append-Only
          </span>
        </div>
      </div>
    </div>
  );
}
