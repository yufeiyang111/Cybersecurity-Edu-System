import { reactive, watch, onMounted } from 'vue'

/**
 * 数字滚动动画：目标值变化时从当前值平滑递增（easeOutCubic）。
 * @param getValue 返回目标值的 getter（自动追踪响应式依赖）
 * @param options.duration 动画时长 ms
 * @param options.decimals 小数位数（如耗时/密度）
 * @returns reactive { display }，模板中可直接使用
 */
export function useAnimatedNumber(getValue, { duration = 900, decimals = 0 } = {}) {
  const state = reactive({
    display: (Number(getValue()) || 0).toFixed(decimals)
  })
  let raf = null

  const animate = () => {
    if (raf) cancelAnimationFrame(raf)
    const target = Number(getValue()) || 0
    if (Number(state.display) === target) return
    const start = performance.now()

    const tick = (now) => {
      const progress = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - progress, 3)
      state.display = (target * eased).toFixed(decimals)
      if (progress < 1) {
        raf = requestAnimationFrame(tick)
      }
    }
    raf = requestAnimationFrame(tick)
  }

  onMounted(animate)
  watch(getValue, animate)

  return state
}
