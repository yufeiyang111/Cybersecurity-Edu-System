<template>
  <aside class="chat-sidebar" :class="{ collapsed }">
    <div class="cs-brand">
      <div class="cs-brand-mark">
        <svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="1.8">
          <path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3z" />
          <path d="M9.5 12l2 2 3.5-4" />
        </svg>
      </div>
      <span class="cs-brand-name">AI 安全助手</span>
      <span class="cs-spacer"></span>
      <button class="cs-icon-btn" title="收起侧边栏" @click="$emit('toggle-collapse')">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M15 6l-6 6 6 6" /></svg>
      </button>
    </div>

    <div class="cs-new-wrap">
      <button class="cs-new-btn" @click="$emit('new-chat')">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M12 5v14M5 12h14" /></svg>
        <span class="cs-new-label">新建会话</span>
      </button>
    </div>

    <div class="cs-search-wrap">
      <div class="cs-search">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></svg>
        <input v-model="keyword" type="text" placeholder="搜索会话">
      </div>
    </div>

    <div class="cs-list" @scroll="maybeLoadMore">
      <div v-for="group in visibleGroups" :key="group.key" class="cs-group">
        <button class="cs-group-title" :aria-expanded="!collapsedGroups[group.key]" @click="toggleGroup(group.key)">
          <svg class="cs-group-toggle-icon" :class="{ collapsed: collapsedGroups[group.key] }" viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M6 9l6 6 6-6" /></svg>
          {{ group.label }}
          <span class="cs-count">{{ group.items.length }}</span>
        </button>
        <template v-if="!collapsedGroups[group.key]"><div
          v-for="conv in group.items"
          :key="conv.id"
          class="cs-item"
          v-memo="[conv.id, conv.title, conv.updated_at, conv.id === activeId]"
          :class="{ active: conv.id === activeId }"
          @click="$emit('select', conv.id)"
        >
          <svg class="cs-item-icon" viewBox="0 0 24 24" fill="none" stroke-width="1.6">
            <path d="M12 4l8 4-8 4-8-4 8-4z" /><path d="M4 12v4c0 1.5 3.6 3 8 3s8-1.5 8-3v-4" />
          </svg>
          <span class="cs-item-title">{{ conv.title || '新会话' }}</span>
          <span class="cs-item-ops">
            <button title="重命名" @click.stop="$emit('rename', conv)">
              <svg viewBox="0 0 24 24" fill="none" stroke-width="1.6"><path d="M4 20h4L19 9l-4-4L4 16v4z" /><path d="M13.5 6.5l4 4" /></svg>
            </button>
            <button title="删除" @click.stop="$emit('delete', conv)">
              <svg viewBox="0 0 24 24" fill="none" stroke-width="1.6"><path d="M4 7h16M9 7V5h6v2m-8 0l1 13h8l1-13" /></svg>
            </button>
          </span>
        </div></template>
      </div>
      <div v-if="!conversations.length" class="cs-empty">暂无会话记录</div>
      <div v-if="conversations.length" ref="moreSentinel" class="cs-more-sentinel">
        <span v-if="loadingMore" class="cs-more-tip">加载更早会话…</span>
      </div>
    </div>

    <div class="cs-footer">
      <div class="cs-kb-status">
        <span class="cs-dot"></span>
        <span class="cs-kb-text">{{ kbText }}</span>
        <span v-if="kbCount !== null" class="cs-kb-count">{{ kbCount }} 篇文档</span>
      </div>
      <div class="cs-account" @click.stop="toggleMenu">
        <img v-if="userStore.user?.avatar_url" class="cs-avatar cs-avatar-image" :src="userStore.user.avatar_url" alt="">
        <div v-else class="cs-avatar">{{ userInitial }}</div>
        <div class="cs-account-meta">
          <div class="cs-name">{{ displayName }}</div>
          <div class="cs-email">{{ email }}</div>
        </div>
        <button class="cs-menu-btn">
          <svg viewBox="0 0 24 24" fill="none" stroke-width="1.6">
            <circle cx="5" cy="12" r="1.5" /><circle cx="12" cy="12" r="1.5" /><circle cx="19" cy="12" r="1.5" />
          </svg>
        </button>
      </div>
    </div>

    <div v-if="menuOpen" class="cs-menu-pop" @click.stop>
      <div class="cs-menu-item" @click="goProfile">个人资料</div>
       <div class="cs-menu-item" @click="goSettings">设置</div>
      <div class="cs-menu-item" @click="goHelp">帮助与文档</div>
      <div class="cs-menu-sep"></div>
      <div class="cs-menu-item danger" @click="logout">退出登录</div>
    </div>
  </aside>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { knowledgeAPI } from '@/api'
import { ElMessage } from 'element-plus'

const props = defineProps({
  conversations: { type: Array, default: () => [] },
  activeId: { type: Number, default: null },
  collapsed: { type: Boolean, default: false },
  loadingMore: { type: Boolean, default: false },
  hasMore: { type: Boolean, default: false }
})

const emit = defineEmits(['new-chat', 'select', 'rename', 'delete', 'toggle-collapse', 'open-settings', 'load-more'])

const router = useRouter()
const userStore = useUserStore()
const keyword = ref('')
const menuOpen = ref(false)
const kbCount = ref(null)
const collapsedGroups = reactive({ earlier: true })
const moreSentinel = ref(null)

// 哨兵进入视口且还有更早会话时触发加载；由滚动事件和状态变化共同驱动，
// 避免 IntersectionObserver 只在边界 crossing 时回调导致"哨兵持续可见却不加载"的死锁
const maybeLoadMore = () => {
  if (!props.hasMore || props.loadingMore) return
  if (!moreSentinel.value) return
  const rect = moreSentinel.value.getBoundingClientRect()
  const viewportH = window.innerHeight || document.documentElement.clientHeight
  if (rect.top < viewportH && rect.bottom > 0) {
    emit('load-more')
  }
}

// 列表长度 / 加载状态变化后重新检查：列表不足一屏时自动补加载直到填满或全部加载完
watch(
  () => [props.conversations.length, props.loadingMore, props.hasMore],
  maybeLoadMore
)

const displayName = computed(() => userStore.user?.nickname || userStore.user?.username || '安全管理员')
const email = computed(() => userStore.user?.email || '')
const userInitial = computed(() => (displayName.value || '安')[0])

const kbText = computed(() => (kbCount.value === null ? '知识库已连接' : '知识库已连接 ·'))

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return props.conversations
  return props.conversations.filter(c => (c.title || '').toLowerCase().includes(kw))
})

const visibleGroups = computed(() => {
  const startOfToday = new Date()
  startOfToday.setHours(0, 0, 0, 0)
  const groups = { today: [], yesterday: [], week: [], earlier: [] }
  for (const conv of filtered.value) {
    const d = new Date(conv.updated_at || conv.created_at)
    const dayStart = new Date(d.getFullYear(), d.getMonth(), d.getDate())
    const diff = Math.round((startOfToday - dayStart) / 86400000)
    if (Number.isNaN(diff) || diff <= 0) groups.today.push(conv)
    else if (diff === 1) groups.yesterday.push(conv)
    else if (diff < 7) groups.week.push(conv)
    else groups.earlier.push(conv)
  }
  const labels = [
    { key: 'today', label: '今天', items: groups.today },
    { key: 'yesterday', label: '昨天', items: groups.yesterday },
    { key: 'week', label: '近 7 天', items: groups.week },
    { key: 'earlier', label: '更早', items: groups.earlier }
  ]
  return labels.filter(g => g.items.length > 0)
})

const toggleGroup = (groupKey) => {
  collapsedGroups[groupKey] = !collapsedGroups[groupKey]
}

const loadKbCount = async () => {
  try {
    const res = await knowledgeAPI.getKnowledgeList({ per_page: 1 })
    if (res && typeof res.total === 'number') kbCount.value = res.total
  } catch (e) {
    kbCount.value = null
  }
}

const closeMenu = () => { menuOpen.value = false }
const toggleMenu = () => { menuOpen.value = !menuOpen.value }
const goProfile = () => { closeMenu(); router.push('/user/profile') }
const goSettings = () => { closeMenu(); emit('open-settings') }
const goHelp = () => { closeMenu(); router.push('/policy') }
const logout = async () => {
  closeMenu()
  try {
    await userStore.logout()
    router.push('/login')
  } catch (e) {
    ElMessage.error('退出登录失败')
  }
}

onMounted(() => {
  document.addEventListener('click', closeMenu)
  const schedule = window.requestIdleCallback || ((callback) => window.setTimeout(callback, 300))
  schedule(loadKbCount)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', closeMenu)
})
</script>

<style lang="scss" scoped>
.chat-sidebar {
  width: 264px;
  min-width: 264px;
  background: var(--chat-sidebar);
  border-right: 1px solid var(--chat-hairline);
  display: flex;
  flex-direction: column;
  transition: width .18s ease, min-width .18s ease;
  position: relative;
  color: var(--chat-ink);

  &.collapsed {
    width: 64px;
    min-width: 64px;

    .cs-brand-name, .cs-new-label, .cs-search input, .cs-group-title,
    .cs-item-title, .cs-item-ops, .cs-kb-status, .cs-account-meta, .cs-menu-btn { display: none; }
    .cs-brand { justify-content: center; padding: 14px 4px 10px; }
    .cs-spacer { display: none; }
    .cs-icon-btn { flex-shrink: 0; }
    .cs-new-btn { padding: 0; justify-content: center; }
    .cs-search { justify-content: center; padding: 0; }
    .cs-item { justify-content: center; padding: 8px; }
    .cs-account { justify-content: center; }
    .cs-group { margin-bottom: 0; }
    .cs-more-sentinel { display: none; }
  }
}

.cs-more-sentinel {
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.cs-more-tip {
  font-size: 12px;
  color: var(--chat-hollow, #8a94a6);
}

.cs-brand { display: flex; align-items: center; gap: 10px; padding: 14px 12px 10px; }
.cs-brand-mark {
  width: 30px; height: 30px; border-radius: 8px;
  background: var(--chat-accent);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  svg { width: 16px; height: 16px; }
}
.cs-brand-name { font-size: 15px; font-weight: 600; color: var(--chat-ink); white-space: nowrap; }
.cs-spacer { flex: 1; }

.cs-icon-btn {
  width: 28px; height: 28px; border: none; background: transparent;
  border-radius: 8px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  &:hover { background: var(--chat-hover); }
  svg { width: 15px; height: 15px; stroke: var(--chat-hollow); transition: transform .18s; }
}
.chat-sidebar.collapsed .cs-icon-btn svg { transform: rotate(180deg); }

.cs-new-wrap { padding: 4px 12px 10px; }
.cs-new-btn {
  width: 100%; height: 40px;
  display: flex; align-items: center; gap: 8px;
  padding: 0 14px;
  background: var(--chat-canvas);
  border: 1px solid var(--chat-hairline-strong);
  border-radius: var(--chat-radius);
  cursor: pointer;
  font-family: inherit; font-size: 14px; font-weight: 500; color: var(--chat-ink);
  white-space: nowrap;
  &:hover { border-color: rgba(0, 0, 0, 0.28); }
  svg { width: 15px; height: 15px; stroke: var(--chat-ink); flex-shrink: 0; }
  .cs-new-label { flex: 1; text-align: left; }
}

.cs-search-wrap { padding: 0 12px 10px; }
.cs-search {
  width: 100%; height: 34px;
  background: transparent;
  border: 1px solid var(--chat-hairline);
  border-radius: var(--chat-radius);
  display: flex; align-items: center; gap: 8px;
  padding: 0 10px;
  transition: background .15s, border-color .15s;
  &:hover { background: var(--chat-canvas); }
  &:focus-within { background: var(--chat-canvas); border-color: rgba(0, 0, 0, 0.35); }
  svg { width: 14px; height: 14px; stroke: var(--chat-hollow); flex-shrink: 0; }
  input {
    border: none; outline: none; background: transparent;
    font-size: 13px; color: var(--chat-ink); width: 100%;
    &::placeholder { color: var(--chat-hollow); }
  }
}

.cs-list { flex: 1; overflow-y: auto; padding: 2px 8px 8px; }
.cs-group { margin-bottom: 4px; }
.cs-group-title {
  width: 100%; border: 0; background: transparent; cursor: pointer;
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--chat-hollow);
  padding: 10px 10px 4px;
  white-space: nowrap;
  .cs-group-toggle-icon { width: 13px; height: 13px; stroke: var(--chat-hollow); transition: transform .15s ease; flex-shrink: 0; }
  .cs-group-toggle-icon.collapsed { transform: rotate(-90deg); }
}
.cs-count {
  font-size: 11px; color: var(--chat-hollow);
  background: var(--chat-hover); border-radius: 8px;
  padding: 0 6px; line-height: 16px;
}
.cs-item {
  display: flex; align-items: center; gap: 9px;
  padding: 8px 10px;
  border-radius: var(--chat-radius);
  cursor: pointer;
  font-size: 13.5px;
  white-space: nowrap;
  &:hover { background: var(--chat-hover); }
  &.active { background: var(--chat-hover); font-weight: 500; }
  .cs-item-icon { width: 15px; height: 15px; stroke: var(--chat-hollow); flex-shrink: 0; }
  &.active .cs-item-icon { stroke: var(--chat-ink); }
   .cs-item-title { flex: 1; overflow: hidden; color: var(--chat-ink); text-overflow: ellipsis; }
}
.cs-item-ops { display: none; gap: 2px; flex-shrink: 0; }
.cs-item:hover .cs-item-ops { display: flex; }
.cs-item-ops button {
  width: 24px; height: 24px; border: none; background: transparent;
  border-radius: 6px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  &:hover { background: var(--chat-hover); }
  svg { width: 14px; height: 14px; stroke: var(--chat-hollow); }
  &:hover svg { stroke: var(--chat-ink); }
}
.cs-empty { padding: 24px 10px; text-align: center; font-size: 13px; color: var(--chat-hollow); }

.cs-footer {
  border-top: 1px solid var(--chat-hairline);
  padding: 10px 12px 12px;
  display: flex; flex-direction: column; gap: 10px;
}
.cs-kb-status {
  display: flex; align-items: center; gap: 8px;
  font-size: 12px; color: var(--chat-hollow);
  padding: 0 4px; white-space: nowrap;
  .cs-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--chat-ink); opacity: .55; flex-shrink: 0;
  }
  .cs-kb-text { flex-shrink: 0; }
  .cs-kb-count { overflow: hidden; text-overflow: ellipsis; font-size: 11px; opacity: .8; }
}
.cs-account {
  display: flex; align-items: center; gap: 10px;
  padding: 6px 4px;
  border-radius: var(--chat-radius);
  cursor: pointer;
  white-space: nowrap;
  &:hover { background: var(--chat-hover); }
}
.cs-avatar {
  width: 30px; height: 30px; border-radius: 50%; flex-shrink: 0;
  background: #e2e2e0; display: flex; align-items: center; justify-content: center;
   font-size: 13px; font-weight: 600; color: var(--chat-ink);
}
.cs-avatar-image { object-fit: cover; }
.cs-account-meta { flex: 1; min-width: 0; }
.cs-name { font-size: 13.5px; font-weight: 500; color: var(--chat-ink); overflow: hidden; text-overflow: ellipsis; }
.cs-email { font-size: 12px; color: var(--chat-hollow); overflow: hidden; text-overflow: ellipsis; }
.cs-menu-btn {
  width: 26px; height: 26px; border: none; background: transparent;
  border-radius: 7px; cursor: pointer; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  &:hover { background: var(--chat-hover); }
  svg { width: 15px; height: 15px; stroke: var(--chat-hollow); }
}

.cs-menu-pop {
  position: absolute; z-index: 60;
  left: 12px; bottom: 88px;
  background: var(--chat-canvas);
  border: 1px solid var(--chat-hairline);
  border-radius: var(--chat-radius);
  padding: 6px;
  min-width: 200px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
}
.cs-menu-item {
  display: flex; align-items: center;
  padding: 8px 10px; border-radius: 7px;
   font-size: 13.5px; color: var(--chat-ink); cursor: pointer;
  &:hover { background: var(--chat-hover); }
  &.danger { color: var(--chat-ink); }
}
.cs-menu-sep { height: 1px; background: var(--chat-hairline); margin: 5px 8px; }
</style>
