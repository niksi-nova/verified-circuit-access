"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { BrailleCell, BULLET_PATTERN } from "@/components/BrailleCell";
import { StatusStamp } from "@/components/StatusStamp";
import { deriveStatus, loadReview } from "@/lib/reviewState";
import type { ReviewStatus } from "@/lib/types";
import styles from "./LibraryList.module.css";

export interface CircuitSummary {
  id: string;
  componentCount: number;
  flaggedCount: number;
}

type StatusFilter = "all" | ReviewStatus;
type SortKey = "id" | "flagged";

export function LibraryList({ circuits }: { circuits: CircuitSummary[] }) {
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [sortKey, setSortKey] = useState<SortKey>("id");
  const [statuses, setStatuses] = useState<Record<string, ReviewStatus>>({});

  useEffect(() => {
    const next: Record<string, ReviewStatus> = {};
    for (const c of circuits) {
      const review = loadReview(c.id, window.localStorage);
      next[c.id] = deriveStatus(c.flaggedCount, review);
    }
    // localStorage is browser-only; this one-time sync after mount is
    // the standard way to read it without an SSR/client markup mismatch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setStatuses(next);
  }, [circuits]);

  const filtered = useMemo(() => {
    let rows = circuits.filter((c) => c.id.includes(query.trim()));
    if (statusFilter !== "all") {
      rows = rows.filter((c) => (statuses[c.id] ?? "unreviewed") === statusFilter);
    }
    rows = [...rows].sort((a, b) =>
      sortKey === "id"
        ? a.id.localeCompare(b.id)
        : b.flaggedCount - a.flaggedCount || a.id.localeCompare(b.id),
    );
    return rows;
  }, [circuits, query, statusFilter, sortKey, statuses]);

  return (
    <div>
      <div className={styles.controls}>
        <div className={styles.field}>
          <label htmlFor="library-search">Search by id</label>
          <input
            id="library-search"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. 015"
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="library-status">Status</label>
          <select
            id="library-status"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
          >
            <option value="all">All</option>
            <option value="unreviewed">Machine-read</option>
            <option value="needs-check">Needs teacher check</option>
            <option value="teacher-confirmed">Teacher-confirmed</option>
          </select>
        </div>
        <div className={styles.field}>
          <label htmlFor="library-sort">Sort by</label>
          <select
            id="library-sort"
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as SortKey)}
          >
            <option value="id">Id</option>
            <option value="flagged">Flagged count</option>
          </select>
        </div>
      </div>

      <p aria-live="polite" className="visually-hidden">
        {filtered.length} circuits shown
      </p>

      {filtered.length === 0 ? (
        <p className={styles.empty}>No circuits match this search.</p>
      ) : (
        <ul className={styles.list}>
          {filtered.map((c) => (
            <li key={c.id} className={styles.row}>
              <BrailleCell pattern={BULLET_PATTERN} />
              <span className={styles.id}>{c.id}</span>
              <Link href={`/circuit/${c.id}`} className={styles.link}>
                Circuit {c.id}
              </Link>
              <span className={styles.meta}>{c.componentCount} components</span>
              <span className={styles.meta}>{c.flaggedCount} flagged</span>
              <StatusStamp status={statuses[c.id] ?? "unreviewed"} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
