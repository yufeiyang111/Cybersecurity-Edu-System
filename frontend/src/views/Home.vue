<template>
  <div class="home-page" ref="root">
    <!-- 滚动进度条 -->
    <div class="scrollbar" ref="scrollBar"></div>

    <!-- 顶部导航 -->
    <header class="nav" ref="nav">
      <div class="container nav-inner">
        <div class="logo" @click="$router.push('/')">
          <span class="mark"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l8 4v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-4z"/><path d="M9 12l2 2 4-4"/></svg></span>
          CyberGuard
        </div>
        <nav class="nav-links">
          <router-link to="/" @mouseenter="prefetchRoute('home')">首页</router-link>
          <router-link to="/qa" @mouseenter="prefetchRoute('qa')">智能问答</router-link>
          <router-link to="/knowledge" @mouseenter="prefetchRoute('knowledge')">知识库</router-link>
          <router-link to="/graph" @mouseenter="prefetchRoute('graph')">知识图谱</router-link>
          <router-link to="/security/projects" @mouseenter="prefetchRoute('security')">安全工作台</router-link>
        </nav>
        <div class="nav-actions">
          <template v-if="userStore.isLoggedIn">
            <el-dropdown @command="handleUserCommand">
              <span class="user-info">
                <el-avatar :size="32" :src="userStore.user?.avatar_url || undefined">
                  {{ userStore.user?.nickname?.[0] || userStore.user?.username?.[0] || '用户' }}
                </el-avatar>
                <span class="username">{{ userStore.user?.nickname || userStore.user?.username }}</span>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="profile">
                    <el-icon><User /></el-icon>个人中心
                  </el-dropdown-item>
                  <el-dropdown-item command="history">
                    <el-icon><ChatDotRound /></el-icon>问答历史
                  </el-dropdown-item>
                  <el-dropdown-item command="favorites">
                    <el-icon><Star /></el-icon>我的收藏
                  </el-dropdown-item>
                  <el-dropdown-item v-if="userStore.isAdmin" command="admin">
                    <el-icon><Setting /></el-icon>管理后台
                  </el-dropdown-item>
                  <el-dropdown-item divided command="logout">
                    <el-icon><SwitchButton /></el-icon>退出登录
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
          <template v-else>
            <a class="btn" href="#" @click.prevent="$router.push('/login')">登录</a>
            <a class="btn btn-primary" href="#" @click.prevent="$router.push('/register')">注册</a>
          </template>
        </div>
      </div>
    </header>

    <!-- Hero -->
    <section class="hero" ref="hero">
      <div class="container hero-inner">
        <div class="hero-left" ref="heroLeft">
          <div class="hero-badge"><span class="dot"></span>新一代智能安全知识平台</div>
          <h1 class="hero-title">
            <span class="line">网络安全智能问答</span>
            <span class="line"><span class="brand">教学系统</span></span>
          </h1>
          <p class="hero-desc">基于检索增强生成（RAG）与大语言模型（LLM）的智能问答平台，回答附带知识库引用来源，为您提供精准、专业的网络安全知识解答。</p>
          <div class="hero-actions">
            <a v-if="userStore.isLoggedIn" class="btn btn-primary btn-lg" href="#" @click.prevent="$router.push('/security/projects')">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l8 4v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-4z"/><path d="M9 12l2 2 4-4"/></svg>
              安全工作台
            </a>
            <a class="btn btn-primary btn-lg" href="#" @click.prevent="$router.push('/qa')">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
              开始提问
            </a>
            <a class="btn btn-dark btn-lg" href="#" @click.prevent="$router.push('/knowledge')">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
              浏览知识库
            </a>
          </div>
        </div>

        <div class="hero-right" ref="heroRight">
          <div class="qa-preview">
            <div class="head"><span class="dot"></span>智能问答 · 回答引用示例</div>
            <div class="q">
              <div class="icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></div>
              <div>
                <div class="label">问题</div>
                <div class="text">SQL 注入是如何发生的？</div>
              </div>
            </div>
            <p class="a" ref="typeText"></p>
            <div class="refs" ref="refsEl">
              <div class="ref">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>
                引用：SQL 注入攻击原理与防护
                <span class="src">知识库 · 入门</span>
              </div>
              <div class="ref">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>
                引用：OWASP 注入防护备忘单
                <span class="src">知识库 · 进阶</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 统计 -->
    <section class="stats">
      <div class="container stats-grid">
        <div class="stat reveal">
          <div class="ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><path d="M8 9h8"/><path d="M8 13h5"/></svg></div>
          <div class="body">
            <div class="lbl">累计提问</div>
            <div class="val"><span class="count" :data-target="questions">0</span><small>次</small></div>
          </div>
        </div>
        <div class="stat reveal d1">
          <div class="ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/></svg></div>
          <div class="body">
            <div class="lbl">知识收藏</div>
            <div class="val"><span class="count" :data-target="favorites">0</span><small>条</small></div>
          </div>
        </div>
        <div class="stat reveal d2">
          <div class="ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg></div>
          <div class="body">
            <div class="lbl">累计回答</div>
            <div class="val"><span class="count" :data-target="answers">0</span><small>次</small></div>
          </div>
        </div>
      </div>
    </section>

    <!-- 核心功能 -->
    <section class="section">
      <div class="container">
        <div class="section-head reveal">
          <div>
            <h2 class="section-title">核心功能</h2>
            <p class="section-desc">四个模块覆盖从提问到沉淀的完整学习链路。</p>
          </div>
        </div>
        <div class="features-grid">
          <div class="feature-card reveal">
            <div class="feature-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><path d="M8 9h8"/><path d="M8 13h5"/></svg></div>
            <h3>智能问答</h3>
            <p>基于 RAG 技术，融合向量检索与知识图谱，回答附带引用来源，提供精准的专业答案</p>
          </div>
          <div class="feature-card reveal d1">
            <div class="feature-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg></div>
            <h3>知识库管理</h3>
            <p>系统化的网络安全知识分类，支持多维度检索与浏览</p>
          </div>
          <div class="feature-card reveal d2">
            <div class="feature-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="5" cy="6" r="2.5"/><circle cx="19" cy="6" r="2.5"/><circle cx="12" cy="19" r="2.5"/><path d="M7.2 7.2l3.3 9.6"/><path d="M16.8 7.2l-3.3 9.6"/><path d="M7.5 6h9"/></svg></div>
            <h3>知识图谱</h3>
            <p>可视化展示知识点关联，支持多跳推理与关系探索</p>
          </div>
          <div class="feature-card reveal d3">
            <div class="feature-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg></div>
            <h3>学习历史</h3>
            <p>保存问答记录，支持收藏与回顾，让学习更连贯</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 使用步骤 -->
    <section class="section section-soft">
      <div class="container">
        <div class="section-head reveal">
          <div>
            <h2 class="section-title">如何使用</h2>
            <p class="section-desc">三步开始你的安全知识学习。</p>
          </div>
        </div>
        <div class="steps-grid">
          <div class="step reveal">
            <div class="num">01</div>
            <h3>注册账号</h3>
            <p>填写用户名与密码即可完成注册，无需邮箱验证，即刻开始学习。</p>
          </div>
          <div class="step reveal d1">
            <div class="num">02</div>
            <h3>提出安全问题</h3>
            <p>在智能问答中描述你的问题，系统将结合知识库与知识图谱给出带引用的回答。</p>
          </div>
          <div class="step reveal d2">
            <div class="num">03</div>
            <h3>收藏与回顾</h3>
            <p>收藏重要知识，通过学习历史随时回顾，形成完整的学习闭环。</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 热门知识 -->
    <section class="section">
      <div class="container">
        <div class="section-head reveal">
          <div>
            <h2 class="section-title">热门知识</h2>
            <p class="section-desc">按浏览热度排序，数据来自知识库接口。</p>
          </div>
          <a class="btn" href="#" @click.prevent="$router.push('/knowledge')">查看全部</a>
        </div>
        <div class="hot-grid">
          <template v-if="hotItems.length">
            <div
              v-for="(item, index) in hotItems"
              :key="item.id"
              class="hot-card"
              :class="['reveal', `d${(index % 4) + 1}`]"
              @click="$router.push(`/knowledge/${item.id}`)"
            >
              <div class="hot-tag">
                <span class="tag tag-cat">{{ item.category_name || '未分类' }}</span>
                <span class="tag" :class="difficultyClass[item.difficulty] || 'tag-cat'">
                  {{ difficultyText[item.difficulty] || '普通' }}
                </span>
              </div>
              <h4 class="hot-title">{{ item.title || '（无标题）' }}</h4>
              <p class="hot-summary">{{ item.summary || '暂无摘要' }}</p>
              <div class="hot-meta">
                <span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>{{ item.view_count || 0 }}</span>
                <span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/></svg>{{ item.favorite_count || 0 }}</span>
              </div>
            </div>
          </template>
          <div v-else class="hot-empty">暂无热门知识</div>
        </div>
      </div>
    </section>

    <!-- CTA -->
    <section class="cta">
      <div class="container">
        <div class="cta-inner reveal">
          <h2>开始你的安全知识学习</h2>
          <p>{{ userStore.isLoggedIn ? '立即使用智能问答、知识库与知识图谱。' : '注册账号，立即使用智能问答、知识库与知识图谱。' }}</p>
          <a
            class="btn btn-primary"
            href="#"
            style="padding:11px 28px;"
            @click.prevent="$router.push(userStore.isLoggedIn ? '/qa' : '/register')"
          >
            {{ userStore.isLoggedIn ? '开始提问' : '免费注册' }}
          </a>
        </div>
      </div>
    </section>

    <!-- Footer -->
    <footer class="footer">
      <div>CyberGuard 网络安全智能问答教学系统 © 2024 · <a href="#" @click.prevent>用户协议</a> · <a href="#" @click.prevent>隐私政策</a> · <a href="#" @click.prevent>联系我们</a></div>
    </footer>

    <!-- 返回顶部 -->
    <button class="to-top" ref="toTop" aria-label="返回顶部" @click="scrollTop">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5"/><path d="M5 12l7-7 7 7"/></svg>
    </button>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { knowledgeAPI } from '@/api'
import { ElMessage } from 'element-plus'
import { User, ChatDotRound, Star, Setting, SwitchButton } from '@element-plus/icons-vue'
import { useProfileStats } from '@/composables/user/useProfileStats'
import { useHomeEffects } from '@/composables/home/useHomeEffects'

const router = useRouter()
const userStore = useUserStore()

const root = ref(null)
const scrollBar = ref(null)
const nav = ref(null)
const toTop = ref(null)
const hero = ref(null)
const heroLeft = ref(null)
const heroRight = ref(null)
const typeText = ref(null)
const refsEl = ref(null)

const hotItems = ref([])
const { questions, favorites, answers, load: loadStats } = useProfileStats()

const difficultyClass = { easy: 'tag-easy', medium: 'tag-mid', hard: 'tag-hard' }
const difficultyText = { easy: '入门', medium: '进阶', hard: '高级' }

const effects = useHomeEffects({ root, scrollBar, nav, toTop, hero, heroLeft, heroRight, typeText, refsEl })

const handleUserCommand = (command) => {
  switch (command) {
    case 'profile':
      router.push('/user/profile')
      break
    case 'history':
      router.push('/user/history')
      break
    case 'favorites':
      router.push('/user/favorites')
      break
    case 'admin':
      router.push('/admin/dashboard')
      break
    case 'logout':
      userStore.logout()
      ElMessage.success('已退出登录')
      router.push('/')
      break
  }
}

const fetchHotKnowledge = async () => {
  try {
    const res = await knowledgeAPI.getHot({ limit: 8 })
    hotItems.value = res.items || []
  } catch (error) {
    console.error('获取热门知识失败:', error)
  }
}

// 悬停导航时预加载目标页 chunk，降低点击后的首屏等待
const prefetchRoute = (name) => {
  const loaders = {
    home: () => import('@/views/Home.vue'),
    qa: () => import('@/views/QA.vue'),
    knowledge: () => import('@/views/Knowledge.vue'),
    graph: () => import('@/views/KnowledgeGraph.vue'),
    security: () => import('@/views/SecurityWorkbenchLayout.vue')
  }
  loaders[name]?.().catch(() => {})
}

const scrollTop = () => window.scrollTo({ top: 0, behavior: 'smooth' })

onMounted(async () => {
  setTimeout(() => effects.start(), 80)
  await fetchHotKnowledge()
  effects.refresh()
  setTimeout(() => {
    loadStats().then(() => effects.refresh())
  }, 800)
})
</script>

<style lang="scss">
:root {
  --home-brand: #2ea44f;
  --home-brand-hover: #2c974b;
  --home-brand-soft: rgba(46, 164, 79, 0.12);
  --home-dark-0: #0d1117;
  --home-dark-1: #161b22;
  --home-dark-2: #21262d;
  --home-dark-line: #30363d;
  --home-dark-text: #c9d1d9;
  --home-dark-muted: #8b949e;
  --home-bg-soft: #f6f8fa;
  --home-line: #d0d7de;
  --home-line-soft: #d8dee4;
  --home-fg: #24292f;
  --home-fg-2: #57606a;
  --home-fg-3: #8c959f;
  --home-ease: cubic-bezier(0.22, 1, 0.36, 1);
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
  .reveal,
  .hero-title .line,
  .hero-desc,
  .hero-actions,
  .hero-badge,
  .qa-preview {
    opacity: 1 !important;
    transform: none !important;
  }
}
</style>

<style lang="scss" scoped>
.home-page {
  min-height: 100vh;
  background: #fff;
  font-size: 15px;
  line-height: 1.7;
  color: var(--home-fg);
  -webkit-font-smoothing: auto;
  overflow-x: hidden;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
}

/* 滚动进度条 */
.scrollbar {
  position: fixed;
  top: 0;
  left: 0;
  height: 3px;
  width: 0;
  background: linear-gradient(90deg, var(--home-brand), #4fd66e);
  z-index: 300;
}

/* 返回顶部 */
.to-top {
  position: fixed;
  right: 26px;
  bottom: 26px;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: 1px solid var(--home-dark-line);
  background: var(--home-dark-1);
  color: var(--home-dark-text);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 150;
  opacity: 0;
  transform: translateY(14px);
  pointer-events: none;
  transition: opacity 0.35s var(--home-ease), transform 0.35s var(--home-ease), background 0.35s, border-color 0.35s;
}
.to-top.show {
  opacity: 1;
  transform: translateY(0);
  pointer-events: auto;
}
.to-top:hover {
  border-color: var(--home-brand);
  color: #fff;
  background: var(--home-brand);
  transform: translateY(-3px);
}
.to-top svg {
  width: 17px;
  height: 17px;
}

/* 滚动渐显 */
.reveal {
  opacity: 0;
  transform: translateY(26px);
  transition: opacity 0.7s var(--home-ease), transform 0.7s var(--home-ease);
}
.reveal.in {
  opacity: 1;
  transform: translateY(0);
}
.reveal.d1 { transition-delay: 0.08s; }
.reveal.d2 { transition-delay: 0.16s; }
.reveal.d3 { transition-delay: 0.24s; }
.reveal.d4 { transition-delay: 0.32s; }

/* 导航 */
.nav {
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--home-line-soft);
  position: sticky;
  top: 0;
  z-index: 100;
  animation: homeNavIn 0.6s var(--home-ease) both;
  transition: background 0.3s, box-shadow 0.3s;
}
.nav.scrolled {
  background: rgba(255, 255, 255, 0.97);
  box-shadow: 0 1px 10px rgba(22, 27, 34, 0.1);
}
@keyframes homeNavIn {
  from { transform: translateY(-100%); }
  to { transform: translateY(0); }
}
.nav-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
}
.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 20px;
  font-weight: 600;
  color: var(--home-fg);
  cursor: pointer;
}
.logo .mark {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: var(--home-brand);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.3s var(--home-ease);
}
.logo:hover .mark {
  transform: rotate(-8deg) scale(1.08);
}
.nav-links {
  display: flex;
  gap: 30px;
}
.nav-links a {
  font-size: 15px;
  color: var(--home-fg-2);
  position: relative;
  padding: 4px 0;
  text-decoration: none;
  transition: color 0.2s;
}
.nav-links a::after {
  content: '';
  position: absolute;
  left: 0;
  bottom: -2px;
  width: 100%;
  height: 2px;
  background: var(--home-brand);
  border-radius: 2px;
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.3s var(--home-ease);
}
.nav-links a:hover {
  color: var(--home-brand);
  text-decoration: none;
}
.nav-links a:hover::after,
.nav-links a.router-link-active::after {
  transform: scaleX(1);
}
.nav-links a.router-link-active {
  color: var(--home-brand);
}
.nav-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  outline: none;
}
.user-info .username {
  color: var(--home-fg-2);
  font-size: 14px;
}

/* 按钮 */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 8px 18px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  border: 1px solid var(--home-line);
  background: var(--home-bg-soft);
  color: var(--home-fg);
  position: relative;
  overflow: hidden;
  transition: transform 0.25s var(--home-ease), background 0.25s, border-color 0.25s, color 0.25s;
}
.btn svg {
  width: 15px;
  height: 15px;
  transition: transform 0.25s var(--home-ease);
}
.btn:hover {
  background: #eaeef2;
  transform: translateY(-1px);
}
.btn:hover svg {
  transform: translateX(2px);
}
.btn-primary {
  background: var(--home-brand);
  border-color: var(--home-brand);
  color: #fff;
  font-weight: 600;
}
.btn-primary:hover {
  background: var(--home-brand-hover);
  border-color: var(--home-brand-hover);
  color: #fff;
}
.btn-primary::before {
  content: '';
  position: absolute;
  top: 0;
  left: -80%;
  width: 60%;
  height: 100%;
  background: linear-gradient(110deg, transparent, rgba(255, 255, 255, 0.28), transparent);
  transform: skewX(-20deg);
  transition: left 0.55s var(--home-ease);
}
.btn-primary:hover::before {
  left: 120%;
}
.btn-lg {
  padding: 12px 30px;
  font-size: 16px;
}
:deep(.btn .ripple) {
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.35);
  transform: scale(0);
  animation: homeRipple 0.6s ease-out forwards;
  pointer-events: none;
}
:deep(.btn-dark .ripple) {
  background: rgba(46, 164, 79, 0.3);
}
@keyframes homeRipple {
  to { transform: scale(3); opacity: 0; }
}

/* Hero */
.hero {
  background: linear-gradient(180deg, var(--home-dark-1) 0%, var(--home-dark-0) 100%);
  color: var(--home-dark-text);
  padding: 84px 0;
  position: relative;
  overflow: hidden;
}
.hero::before {
  content: '';
  position: absolute;
  width: 520px;
  height: 520px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(46, 164, 79, 0.14), transparent 65%);
  top: -200px;
  right: -120px;
  animation: homeBreathe 7s ease-in-out infinite;
}
@keyframes homeBreathe {
  0%, 100% { opacity: 0.7; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.12); }
}
.hero::after {
  content: '';
  position: absolute;
  inset: -28px 0 0 0;
  background-image: radial-gradient(rgba(240, 246, 252, 0.055) 1px, transparent 1px);
  background-size: 28px 28px;
  animation: homeGridDrift 36s linear infinite;
  pointer-events: none;
}
@keyframes homeGridDrift {
  to { transform: translateY(28px); }
}
.hero-inner {
  display: grid;
  grid-template-columns: 1.02fr 0.98fr;
  gap: 52px;
  align-items: center;
  position: relative;
}
.hero-left,
.hero-right {
  transition: transform 0.35s var(--home-ease);
}
.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  color: #7ee2a8;
  background: rgba(46, 164, 79, 0.1);
  border: 1px solid rgba(46, 164, 79, 0.35);
  padding: 5px 14px;
  border-radius: 999px;
  margin-bottom: 18px;
  opacity: 0;
  transform: translateY(18px);
  animation: homeTitleUp 0.7s var(--home-ease) 0.05s forwards;
}
.hero-badge .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #2ea44f;
  animation: homeBadgePing 2.2s ease-out infinite;
}
@keyframes homeBadgePing {
  0% { box-shadow: 0 0 0 0 rgba(46, 164, 79, 0.55); }
  70%, 100% { box-shadow: 0 0 0 7px rgba(46, 164, 79, 0); }
}
.hero-title {
  font-size: 42px;
  font-weight: 700;
  line-height: 1.28;
  color: #f0f6fc;
  margin-bottom: 18px;
  letter-spacing: -0.01em;
}
.hero-title .line {
  display: block;
  opacity: 0;
  transform: translateY(30px);
  animation: homeTitleUp 0.8s var(--home-ease) forwards;
}
.hero-title .line:nth-child(1) { animation-delay: 0.15s; }
.hero-title .line:nth-child(2) { animation-delay: 0.3s; }
@keyframes homeTitleUp {
  to { opacity: 1; transform: translateY(0); }
}
.hero-title .brand {
  color: var(--home-brand);
}
.hero-desc {
  font-size: 17px;
  line-height: 1.8;
  color: var(--home-dark-muted);
  margin-bottom: 30px;
  max-width: 44ch;
  opacity: 0;
  transform: translateY(24px);
  animation: homeTitleUp 0.8s var(--home-ease) 0.45s forwards;
}
.hero-actions {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  opacity: 0;
  transform: translateY(24px);
  animation: homeTitleUp 0.8s var(--home-ease) 0.6s forwards;
}
.btn-dark {
  background: transparent;
  border-color: var(--home-dark-line);
  color: var(--home-dark-text);
}
.btn-dark:hover {
  border-color: var(--home-brand);
  color: #fff;
  background: var(--home-brand-soft);
}

/* 问答卡 */
.qa-preview {
  background: var(--home-dark-2);
  border: 1px solid var(--home-dark-line);
  border-radius: 12px;
  padding: 24px;
  opacity: 0;
  transform: translateY(30px) scale(0.98);
  animation: homeCardIn 0.9s var(--home-ease) 0.35s forwards, homeFloaty 7s ease-in-out 2.6s infinite;
}
@keyframes homeCardIn {
  to { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes homeFloaty {
  0%, 100% { transform: translateY(0) scale(1); }
  50% { transform: translateY(-8px) scale(1); }
}
.qa-preview .head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--home-dark-line);
  margin-bottom: 16px;
  font-size: 13px;
  color: var(--home-dark-muted);
}
.qa-preview .head .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--home-brand);
  animation: homePulseDot 2s ease-in-out infinite;
}
@keyframes homePulseDot {
  0%, 100% { box-shadow: 0 0 0 0 rgba(46, 164, 79, 0.5); }
  50% { box-shadow: 0 0 0 6px rgba(46, 164, 79, 0); }
}
.qa-preview .q {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin-bottom: 14px;
}
.qa-preview .q .icon {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: var(--home-brand-soft);
  border: 1px solid rgba(46, 164, 79, 0.3);
  color: var(--home-brand);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.qa-preview .q .icon svg {
  width: 16px;
  height: 16px;
}
.qa-preview .q .label {
  font-size: 12px;
  color: var(--home-dark-muted);
  margin-bottom: 2px;
}
.qa-preview .q .text {
  font-size: 14.5px;
  font-weight: 600;
  color: #f0f6fc;
}
.qa-preview .a {
  font-size: 13.5px;
  color: var(--home-dark-text);
  line-height: 1.7;
  margin-bottom: 14px;
  min-height: 46px;
}
.qa-preview .refs {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.qa-preview .ref {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  color: var(--home-dark-text);
  background: var(--home-dark-1);
  border: 1px solid var(--home-dark-line);
  border-radius: 6px;
  padding: 7px 12px;
  opacity: 0;
  transform: translateX(-14px);
  transition: opacity 0.5s var(--home-ease), transform 0.5s var(--home-ease), border-color 0.3s;
}
.qa-preview .ref svg {
  width: 13px;
  height: 13px;
  color: var(--home-brand);
  flex-shrink: 0;
  transition: transform 0.3s var(--home-ease);
}
.qa-preview .ref .src {
  color: #6e7681;
  margin-left: auto;
  font-size: 12px;
}
.qa-preview .ref:hover {
  border-color: rgba(46, 164, 79, 0.4);
}
.qa-preview .ref:hover svg {
  transform: translateY(-1px);
}

/* 统计 */
.stats {
  padding: 40px 0 0;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.stat {
  background: #fff;
  border: 1px solid var(--home-line);
  border-radius: 10px;
  padding: 20px 22px;
  display: flex;
  align-items: center;
  gap: 14px;
  transition: transform 0.3s var(--home-ease), border-color 0.3s, box-shadow 0.3s;
}
.stat:hover {
  border-color: rgba(46, 164, 79, 0.4);
  transform: translateY(-3px);
  box-shadow: 0 10px 24px rgba(22, 27, 34, 0.08);
}
.stat .ico {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: var(--home-bg-soft);
  border: 1px solid var(--home-line-soft);
  color: var(--home-brand);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: transform 0.3s var(--home-ease);
}
.stat:hover .ico {
  transform: scale(1.1) rotate(-4deg);
  background: var(--home-brand-soft);
}
.stat .ico svg {
  width: 19px;
  height: 19px;
}
.stat .body {
  flex: 1;
}
.stat .lbl {
  font-size: 12.5px;
  color: var(--home-fg-3);
  margin-bottom: 2px;
}
.stat .val {
  font-size: 23px;
  font-weight: 700;
  letter-spacing: -0.01em;
  font-variant-numeric: tabular-nums;
}
.stat .val small {
  font-size: 12px;
  color: var(--home-fg-3);
  font-weight: 400;
  margin-left: 3px;
}

/* 区块 */
.section {
  padding: 72px 0;
}
.section-soft {
  background: var(--home-bg-soft);
  border-top: 1px solid var(--home-line-soft);
  border-bottom: 1px solid var(--home-line-soft);
}
.section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 34px;
  flex-wrap: wrap;
  gap: 12px;
}
.section-title {
  font-size: 28px;
  font-weight: 600;
  color: var(--home-fg);
  margin: 0;
  letter-spacing: -0.01em;
  position: relative;
  display: inline-block;
}
.section-title::after {
  content: '';
  position: absolute;
  left: 0;
  bottom: -6px;
  height: 3px;
  width: 46px;
  border-radius: 3px;
  background: linear-gradient(90deg, var(--home-brand), #4fd66e);
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.5s var(--home-ease) 0.25s;
}
.section-head.reveal.in .section-title::after {
  transform: scaleX(1);
}
.section-desc {
  font-size: 14.5px;
  color: var(--home-fg-2);
  margin-top: 8px;
}

/* 核心功能 */
.features-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}
.feature-card {
  background: #fff;
  border: 1px solid var(--home-line);
  border-radius: 10px;
  padding: 30px 26px;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
  transition: transform 0.35s var(--home-ease), border-color 0.35s, box-shadow 0.35s;
}
.feature-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--home-brand), #4fd66e);
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.4s var(--home-ease);
}
.feature-card:hover {
  border-color: rgba(46, 164, 79, 0.45);
  transform: translateY(-5px);
  box-shadow: 0 14px 30px rgba(22, 27, 34, 0.1);
}
.feature-card:hover::before {
  transform: scaleX(1);
}
.feature-icon {
  width: 50px;
  height: 50px;
  border-radius: 10px;
  background: var(--home-bg-soft);
  border: 1px solid var(--home-line-soft);
  color: var(--home-brand);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 18px;
  transition: transform 0.35s var(--home-ease), background 0.35s, border-color 0.35s;
  animation: homeIconBob 4.5s ease-in-out infinite;
}
.feature-card:nth-child(2) .feature-icon { animation-delay: 0.6s; }
.feature-card:nth-child(3) .feature-icon { animation-delay: 1.2s; }
.feature-card:nth-child(4) .feature-icon { animation-delay: 1.8s; }
@keyframes homeIconBob {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
}
.feature-icon svg {
  width: 23px;
  height: 23px;
  transition: transform 0.35s var(--home-ease);
}
.feature-card:hover .feature-icon {
  background: var(--home-brand-soft);
  border-color: rgba(46, 164, 79, 0.3);
}
.feature-card:hover .feature-icon svg {
  transform: scale(1.12) rotate(-4deg);
}
.feature-card h3 {
  font-size: 17px;
  font-weight: 600;
  color: var(--home-fg);
  margin-bottom: 8px;
  transition: color 0.25s;
}
.feature-card:hover h3 {
  color: var(--home-brand-hover);
}
.feature-card p {
  font-size: 13.5px;
  color: var(--home-fg-2);
  line-height: 1.7;
  flex: 1;
  margin: 0;
}

/* 使用步骤 */
.steps-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}
.step {
  background: #fff;
  border: 1px solid var(--home-line);
  border-radius: 10px;
  padding: 28px 26px;
  transition: transform 0.35s var(--home-ease), border-color 0.35s, box-shadow 0.35s;
}
.step:hover {
  border-color: rgba(46, 164, 79, 0.4);
  transform: translateY(-4px);
  box-shadow: 0 12px 28px rgba(22, 27, 34, 0.08);
}
.step .num {
  font-size: 30px;
  font-weight: 700;
  color: #e6eaf0;
  margin-bottom: 16px;
  letter-spacing: -0.02em;
  display: inline-block;
  transition: all 0.35s var(--home-ease);
}
.step:hover .num {
  color: var(--home-brand);
  transform: translateX(4px);
}
.step.reveal.in .num {
  animation: homeNumPop 0.5s var(--home-ease) 0.1s backwards;
}
@keyframes homeNumPop {
  from { transform: scale(0.6); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}
.step h3 {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 8px;
}
.step p {
  font-size: 13.5px;
  color: var(--home-fg-2);
  line-height: 1.7;
  margin: 0;
}

/* 热门知识 */
.hot-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}
.hot-empty {
  grid-column: 1 / -1;
  padding: 48px 0;
  text-align: center;
  color: var(--home-fg-3);
  font-size: 14px;
}
.hot-card {
  background: #fff;
  border: 1px solid var(--home-line);
  border-radius: 10px;
  padding: 22px;
  cursor: pointer;
  transition: transform 0.35s var(--home-ease), border-color 0.35s, box-shadow 0.35s;
  display: flex;
  flex-direction: column;
}
.hot-card:hover {
  border-color: rgba(46, 164, 79, 0.45);
  transform: translateY(-5px);
  box-shadow: 0 14px 30px rgba(22, 27, 34, 0.1);
}
.hot-tag {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.tag {
  font-size: 12px;
  font-weight: 500;
  padding: 2px 10px;
  border-radius: 999px;
  transition: transform 0.25s var(--home-ease), background 0.25s, color 0.25s, border-color 0.25s;
}
.tag-cat {
  background: var(--home-bg-soft);
  color: var(--home-fg-2);
  border: 1px solid var(--home-line-soft);
}
.tag-easy {
  color: #1a7f37;
  background: rgba(26, 127, 55, 0.1);
  border: 1px solid rgba(26, 127, 55, 0.3);
}
.tag-mid {
  color: #9a6700;
  background: rgba(154, 103, 0, 0.08);
  border: 1px solid rgba(154, 103, 0, 0.3);
}
.tag-hard {
  color: #cf222e;
  background: rgba(207, 34, 46, 0.08);
  border: 1px solid rgba(207, 34, 46, 0.3);
}
.hot-card:hover .tag {
  transform: scale(1.07);
}
.hot-card:hover .tag-cat {
  background: var(--home-brand-soft);
  color: var(--home-brand-hover);
  border-color: rgba(46, 164, 79, 0.3);
}
.hot-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--home-fg);
  margin-bottom: 8px;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  transition: color 0.25s;
}
.hot-card:hover .hot-title {
  color: var(--home-brand-hover);
}
.hot-summary {
  font-size: 13px;
  color: var(--home-fg-2);
  line-height: 1.65;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-bottom: 16px;
}
.hot-meta {
  display: flex;
  gap: 16px;
  font-size: 12.5px;
  color: var(--home-fg-3);
  margin-top: auto;
}
.hot-meta span {
  display: flex;
  align-items: center;
  gap: 5px;
  transition: color 0.25s;
}
.hot-meta svg {
  width: 13px;
  height: 13px;
  transition: transform 0.3s var(--home-ease);
}
.hot-card:hover .hot-meta span {
  color: var(--home-brand-hover);
}
.hot-card:hover .hot-meta svg {
  transform: scale(1.15);
}

/* CTA */
.cta {
  padding: 0 0 72px;
}
.cta-inner {
  background: linear-gradient(180deg, var(--home-dark-1), var(--home-dark-0));
  border-radius: 14px;
  padding: 48px 32px;
  text-align: center;
  color: var(--home-dark-text);
  position: relative;
  overflow: hidden;
}
.cta-inner::before {
  content: '';
  position: absolute;
  width: 380px;
  height: 380px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(46, 164, 79, 0.16), transparent 65%);
  top: -160px;
  left: 50%;
  transform: translateX(-50%);
  animation: homeBreathe 8s ease-in-out infinite;
}
.cta-inner h2 {
  font-size: 26px;
  font-weight: 700;
  color: #f0f6fc;
  margin-bottom: 10px;
  position: relative;
}
.cta-inner p {
  font-size: 14.5px;
  color: var(--home-dark-muted);
  margin-bottom: 24px;
  position: relative;
}

/* Footer */
.footer {
  padding: 28px 0;
  background: var(--home-dark-0);
  color: var(--home-dark-muted);
  text-align: center;
  font-size: 13.5px;
}
.footer a {
  color: #8b949e;
  margin: 0 14px;
  position: relative;
  text-decoration: none;
  transition: color 0.2s;
}
.footer a::after {
  content: '';
  position: absolute;
  left: 0;
  bottom: -2px;
  width: 100%;
  height: 1px;
  background: var(--home-brand);
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.3s var(--home-ease);
}
.footer a:hover {
  color: var(--home-brand);
  text-decoration: none;
}
.footer a:hover::after {
  transform: scaleX(1);
}

@media (max-width: 1024px) {
  .hero-inner {
    grid-template-columns: 1fr;
    gap: 40px;
  }
  .features-grid,
  .hot-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .stats-grid,
  .steps-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 768px) {
  .nav-links {
    display: none;
  }
  .features-grid,
  .hot-grid {
    grid-template-columns: 1fr;
  }
}
</style>
