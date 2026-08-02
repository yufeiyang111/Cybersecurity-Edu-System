import { onBeforeUnmount } from 'vue'

const ANSWER = 'SQL 注入发生在用户输入被直接拼接进 SQL 语句时。攻击者通过构造特殊输入改变查询语义，使数据库执行非预期的操作……'

export function useHomeEffects(refs) {
  const rm = window.matchMedia('(prefers-reduced-motion: reduce)')
  let revealIO = null
  let countedIO = null
  let typeTimer = null
  let typeInterval = null
  let onScroll = null

  function observeReveals() {
    if (revealIO) revealIO.disconnect()
    revealIO = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add('in')
          revealIO.unobserve(e.target)
        }
      })
    }, { threshold: 0.15 })
    refs.root.value?.querySelectorAll('.reveal').forEach((el) => revealIO.observe(el))
  }

  function animateCount(el) {
    const target = parseInt(el.dataset.target || '0', 10)
    const t0 = performance.now()
    function tick(now) {
      const p = Math.min((now - t0) / 900, 1)
      el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)))
      if (p < 1) requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  }

  function observeCounters() {
    if (countedIO) countedIO.disconnect()
    countedIO = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (!e.isIntersecting) return
        countedIO.unobserve(e.target)
        animateCount(e.target)
      })
    }, { threshold: 0.4 })
    refs.root.value?.querySelectorAll('.count').forEach((el) => countedIO.observe(el))
  }

  function startTypewriter() {
    const el = refs.typeText.value
    if (!el) return
    typeTimer = setTimeout(() => {
      let i = 0
      typeInterval = setInterval(() => {
        i++
        el.textContent = ANSWER.slice(0, i)
        if (i >= ANSWER.length) {
          clearInterval(typeInterval)
          refs.refsEl.value?.querySelectorAll('.ref').forEach((r, idx) => {
            setTimeout(() => {
              r.style.opacity = '1'
              r.style.transform = 'translateX(0)'
            }, idx * 180)
          })
        }
      }, 32)
    }, 1400)
  }

  function bindScrollEffects() {
    let ticking = false
    onScroll = () => {
      if (ticking) return
      ticking = true
      requestAnimationFrame(() => {
        const h = document.documentElement
        const max = h.scrollHeight - h.clientHeight
        const p = max > 0 ? (h.scrollTop || window.pageYOffset) / max : 0
        if (refs.scrollBar.value) refs.scrollBar.value.style.width = `${p * 100}%`
        refs.nav.value?.classList.toggle('scrolled', window.pageYOffset > 8)
        refs.toTop.value?.classList.toggle('show', window.pageYOffset > 400)
        ticking = false
      })
    }
    window.addEventListener('scroll', onScroll, { passive: true })
  }

  function bindHeroParallax() {
    if (rm.matches) return
    const hero = refs.hero.value
    if (!hero) return
    let ticking = false
    hero.addEventListener('mousemove', (ev) => {
      if (ticking) return
      ticking = true
      requestAnimationFrame(() => {
        const r = hero.getBoundingClientRect()
        const x = (ev.clientX - r.left) / r.width - 0.5
        const y = (ev.clientY - r.top) / r.height - 0.5
        if (refs.heroLeft.value) refs.heroLeft.value.style.transform = `translate(${x * -10}px, ${y * -8}px)`
        if (refs.heroRight.value) refs.heroRight.value.style.transform = `translate(${x * 8}px, ${y * 6}px)`
        ticking = false
      })
    })
    hero.addEventListener('mouseleave', () => {
      if (refs.heroLeft.value) refs.heroLeft.value.style.transform = ''
      if (refs.heroRight.value) refs.heroRight.value.style.transform = ''
    })

    refs.root.value?.querySelectorAll('.hero-actions .btn').forEach((b) => {
      b.addEventListener('mousemove', (ev) => {
        const r = b.getBoundingClientRect()
        const dx = ev.clientX - r.left - r.width / 2
        const dy = ev.clientY - r.top - r.height / 2
        b.style.transform = `translate(${dx * 0.18}px, ${dy * 0.18}px)`
      })
      b.addEventListener('mouseleave', () => { b.style.transform = '' })
    })

    refs.root.value?.querySelectorAll('.btn').forEach((b) => {
      b.addEventListener('click', (ev) => {
        const r = b.getBoundingClientRect()
        const rip = document.createElement('span')
        rip.className = 'ripple'
        const size = Math.max(r.width, r.height)
        rip.style.width = rip.style.height = `${size}px`
        rip.style.left = `${ev.clientX - r.left - size / 2}px`
        rip.style.top = `${ev.clientY - r.top - size / 2}px`
        b.appendChild(rip)
        rip.addEventListener('animationend', () => rip.remove())
      })
    })
  }

  function start() {
    observeReveals()
    observeCounters()
    startTypewriter()
    bindScrollEffects()
    bindHeroParallax()
  }

  function refresh() {
    observeReveals()
    observeCounters()
  }

  onBeforeUnmount(() => {
    if (revealIO) revealIO.disconnect()
    if (countedIO) countedIO.disconnect()
    if (typeTimer) clearTimeout(typeTimer)
    if (typeInterval) clearInterval(typeInterval)
    if (onScroll) window.removeEventListener('scroll', onScroll)
  })

  return { start, refresh }
}
