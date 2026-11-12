import type { ReviewStatus } from "@/lib/types";
import styles from "./StatusStamp.module.css";

const LABELS: Record<ReviewStatus, string> = {
  unreviewed: "machine-read",
  "needs-check": "needs teacher check",
  "teacher-confirmed": "teacher-confirmed",
};

const CLASS: Record<ReviewStatus, string> = {
  unreviewed: styles.unreviewed,
  "needs-check": styles.needsCheck,
  "teacher-confirmed": styles.confirmed,
};

export function StatusStamp({ status }: { status: ReviewStatus }) {
  return <span className={`${styles.stamp} ${CLASS[status]}`}>{LABELS[status]}</span>;
}
