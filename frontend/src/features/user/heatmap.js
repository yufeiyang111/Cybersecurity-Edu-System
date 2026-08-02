export const HEATMAP_LEVELS = ['#ebedf0', '#9be9a8', '#40c463', '#30a14e', '#216e39']

export function countToLevel(count) {
  if (count <= 0) return 0
  if (count <= 3) return 1
  if (count <= 6) return 2
  if (count <= 10) return 3
  return 4
}

const DAY_MS = 24 * 60 * 60 * 1000
const WEEK_MS = 7 * DAY_MS

// 将真实的活跃事件（[{ date, count }]）归一化为 53 周 x 7 天的网格。
// 未提供真实数据时返回全空网格，由组件展示空态，不生成任何模拟数据。
export function buildHeatmapData(events = [], options = {}) {
  const weeks = options.weeks ?? 53
  const today = options.today ? new Date(options.today) : new Date()

  const todayDow = today.getDay()
  const endDate = new Date(today)
  endDate.setDate(today.getDate() + (6 - todayDow))
  endDate.setHours(0, 0, 0, 0)

  const startDate = new Date(endDate.getTime() - (weeks - 1) * WEEK_MS)
  startDate.setHours(0, 0, 0, 0)

  const countByDate = new Map()
  let total = 0
  for (const ev of events) {
    if (!ev || !ev.date) continue
    const d = new Date(ev.date)
    if (d < startDate || d > today) continue
    const key = d.toDateString()
    const c = (countByDate.get(key) || 0) + (Number(ev.count) || 0)
    countByDate.set(key, c)
  }

  const days = []
  for (let w = 0; w < weeks; w++) {
    const week = []
    for (let d = 0; d < 7; d++) {
      const date = new Date(startDate.getTime() + (w * 7 + d) * DAY_MS)
      const count = countByDate.get(date.toDateString()) || 0
      total += count
      week.push({ date, count, level: countToLevel(count) })
    }
    days.push(week)
  }

  return { days, total, levels: HEATMAP_LEVELS }
}
