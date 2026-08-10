import { computed, nextTick, onMounted, ref } from 'vue'

const STORAGE_KEY = 'security-fab-position'
const EDGE = 24
const ESTIMATED_WIDTH = 240
const ESTIMATED_HEIGHT = 120

export function useFabDrag() {
  const fabEl = ref(null)
  const isDragging = ref(false)
  const didDrag = ref(false)
  const fabX = ref(0)
  const fabY = ref(0)

  let dragStartMouseX = 0
  let dragStartMouseY = 0
  let dragStartFabX = 0
  let dragStartFabY = 0
  const DRAG_THRESHOLD_PX = 3

  const fabStyle = computed(() => ({
    transform: `translate(${fabX.value}px, ${fabY.value}px)`
  }))

  const clampToViewport = () => {
    const el = fabEl.value
    if (!el) return
    const w = el.offsetWidth
    const h = el.offsetHeight
    fabX.value = Math.max(0, Math.min(fabX.value, window.innerWidth - w))
    fabY.value = Math.max(0, Math.min(fabY.value, window.innerHeight - h))
  }

  const startDrag = (clientX, clientY) => {
    dragStartMouseX = clientX
    dragStartMouseY = clientY
    dragStartFabX = fabX.value
    dragStartFabY = fabY.value
    isDragging.value = true
    didDrag.value = false
  }

  const moveDrag = (clientX, clientY) => {
    if (!isDragging.value) return
    const deltaX = clientX - dragStartMouseX
    const deltaY = clientY - dragStartMouseY
    if (!didDrag.value && (Math.abs(deltaX) > DRAG_THRESHOLD_PX || Math.abs(deltaY) > DRAG_THRESHOLD_PX)) {
      didDrag.value = true
    }
    let left = dragStartFabX + deltaX
    let top = dragStartFabY + deltaY
    const el = fabEl.value
    if (el) {
      const w = el.offsetWidth
      const h = el.offsetHeight
      left = Math.max(0, Math.min(left, window.innerWidth - w))
      top = Math.max(0, Math.min(top, window.innerHeight - h))
    }
    fabX.value = left
    fabY.value = top
  }

  const endDrag = () => {
    if (!isDragging.value) return
    isDragging.value = false
    nextTick(() => {
      clampToViewport()
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ x: fabX.value, y: fabY.value }))
      } catch {}
    })
  }

  const onMouseDown = (e) => {
    if (e.button !== 0) return
    e.preventDefault()
    startDrag(e.clientX, e.clientY)
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }

  const onTouchStart = (e) => {
    if (e.touches.length !== 1) return
    startDrag(e.touches[0].clientX, e.touches[0].clientY)
    window.addEventListener('touchmove', onTouchMove, { passive: false })
    window.addEventListener('touchend', onTouchEnd)
  }

  const onMouseMove = (e) => moveDrag(e.clientX, e.clientY)

  const onTouchMove = (e) => {
    if (!isDragging.value) return
    e.preventDefault()
    moveDrag(e.touches[0].clientX, e.touches[0].clientY)
  }

  const onMouseUp = () => {
    endDrag()
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', onMouseUp)
  }

  const onTouchEnd = () => {
    endDrag()
    window.removeEventListener('touchmove', onTouchMove)
    window.removeEventListener('touchend', onTouchEnd)
  }

  onMounted(async () => {
    await nextTick()
    const el = fabEl.value
    if (!el) return

    let saved = null
    try {
      saved = localStorage.getItem(STORAGE_KEY)
    } catch {}
    if (saved) {
      try {
        const pos = JSON.parse(saved)
        if (typeof pos.x === 'number' && typeof pos.y === 'number') {
          fabX.value = pos.x
          fabY.value = pos.y
          clampToViewport()
          return
        }
      } catch {}
    }
    fabX.value = window.innerWidth - el.offsetWidth - EDGE
    fabY.value = window.innerHeight - el.offsetHeight - EDGE
  })

  return {
    fabEl,
    fabX,
    fabY,
    isDragging,
    didDrag,
    fabStyle,
    onMouseDown,
    onTouchStart
  }
}