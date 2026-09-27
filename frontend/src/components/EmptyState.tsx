/**
 * Displayed when a list query returns zero results.
 */
export function EmptyState({
  title = "No results",
  message = "There are no items to display.",
}: {
  title?: string;
  message?: string;
}) {
  return (
    <div className="empty-state">
      <p className="empty-state__icon">📭</p>
      <h3>{title}</h3>
      <p>{message}</p>
    </div>
  );
}
