export const STREAM_FOLLOW_BOTTOM_THRESHOLD = 56

export function isNearStreamBottom(container, threshold = STREAM_FOLLOW_BOTTOM_THRESHOLD) {
  if (!container || !Number.isFinite(container.scrollHeight) || !Number.isFinite(container.scrollTop) || !Number.isFinite(container.clientHeight)) {
    return true
  }

  const distance = container.scrollHeight - container.clientHeight - container.scrollTop
  return distance <= Math.max(0, threshold)
}