interface Props { count?: number; height?: number }
export function SkeletonGrid({ count = 6, height = 90 }: Props) {
  return (
    <div className="skeleton-grid">
      {Array.from({ length: count }).map((_, i) => (
        <span key={i} className="skeleton skeleton-box" style={{ height }} />
      ))}
    </div>
  )
}
