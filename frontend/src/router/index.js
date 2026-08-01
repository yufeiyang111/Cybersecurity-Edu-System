import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/Home.vue'),
    meta: { title: '首页' }
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录', guest: true }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Register.vue'),
    meta: { title: '注册', guest: true }
  },
  {
    path: '/qa',
    name: 'QA',
    component: () => import('@/views/QA.vue'),
    meta: { title: '智能问答' }
  },
  {
    path: '/qa/conversation/:id',
    name: 'Conversation',
    component: () => import('@/views/Conversation.vue'),
    meta: { title: '会话详情', requiresAuth: true }
  },
  {
    path: '/security/projects',
    name: 'SecurityProjects',
    component: () => import('@/views/security/Projects.vue'),
    meta: { title: '安全项目', requiresAuth: true }
  },
  {
    path: '/security/projects/:id',
    name: 'SecurityProjectDetail',
    component: () => import('@/views/security/ProjectDetail.vue'),
    meta: { title: '安全知识治理', requiresAuth: true }
  },
  {
    path: '/security/knowledge',
    name: 'SecurityKnowledge',
    component: () => import('@/views/security/Knowledge.vue'),
    meta: { title: '安全知识治理', requiresAuth: true }
  },
  {
    path: '/knowledge',
    name: 'Knowledge',
    component: () => import('@/views/Knowledge.vue'),
    meta: { title: '知识库' }
  },
  {
    path: '/knowledge/:id',
    name: 'KnowledgeDetail',
    component: () => import('@/views/KnowledgeDetail.vue'),
    meta: { title: '知识详情' }
  },
  {
    path: '/graph',
    name: 'KnowledgeGraph',
    component: () => import('@/views/KnowledgeGraph.vue'),
    meta: { title: '知识图谱' }
  },
  {
    path: '/user',
    component: () => import('@/views/UserLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/user/profile'
      },
      {
        path: 'profile',
        name: 'UserProfile',
        component: () => import('@/views/user/Profile.vue'),
        meta: { title: '个人中心' }
      },
      {
        path: 'history',
        name: 'UserHistory',
        component: () => import('@/views/user/History.vue'),
        meta: { title: '问答历史' }
      },
      {
        path: 'favorites',
        name: 'UserFavorites',
        component: () => import('@/views/user/Favorites.vue'),
        meta: { title: '我的收藏' }
      }
    ]
  },
  {
    path: '/admin',
    component: () => import('@/views/AdminLayout.vue'),
    meta: { requiresAuth: true, admin: true },
    children: [
      {
        path: '',
        redirect: '/admin/dashboard'
      },
      {
        path: 'dashboard',
        name: 'AdminDashboard',
        component: () => import('@/views/admin/Dashboard.vue'),
        meta: { title: '管理后台' }
      },
      {
        path: 'users',
        name: 'AdminUsers',
        component: () => import('@/views/admin/Users.vue'),
        meta: { title: '用户管理' }
      },
      {
        path: 'knowledge',
        name: 'AdminKnowledge',
        component: () => import('@/views/admin/Knowledge.vue'),
        meta: { title: '知识管理' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  document.title = to.meta.title ? `${to.meta.title} - CyberGuard` : 'CyberGuard'
  
  const userStore = useUserStore()
  
  // 需要登录
  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
    return
  }
  
  // 游客访问（已登录用户不能访问）
  if (to.meta.guest && userStore.isLoggedIn) {
    next({ name: 'Home' })
    return
  }
  
  // 管理员权限
  if (to.meta.admin && userStore.user?.role !== 'admin') {
    next({ name: 'Home' })
    return
  }
  
  next()
})

export default router
