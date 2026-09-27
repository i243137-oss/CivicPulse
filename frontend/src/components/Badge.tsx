/**
 * Color-coded badge for status, priority, or category values.
 */

interface BadgeProps {
  label: string;
  variant: "status" | "priority" | "category";
  value: string;
}

export function Badge({ label, variant, value }: BadgeProps) {
  return (
    <span className={`badge badge--${variant} badge--${value}`}>{label}</span>
  );
}
