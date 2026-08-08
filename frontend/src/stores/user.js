import { defineStore } from 'pinia'
import { authAPI } from '@/api'

// 解析 JWT payload 的 exp（秒级时间戳）；非标准 JWT 或解析失败返回 null
function parseJwtExp(token) {
  try {
    const payload = token.split('.')[1]
    if (!payload) return null
    let base64 = payload.replace(/-/g, '+').replace(/_/g, '/')
    while (base64.length % 4 !== 0) base64 += '='
    const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0))
    const json = JSON.parse(new TextDecoder().decode(bytes))
    return typeof json.exp === 'number' ? json.exp : null
  } catch (e) {
    return null
  }
}

export const useUserStore = defineStore('user', {
  state: () => ({
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    token: localStorage.getItem('token') || null,
    loading: false
  }),
  
  getters: {
    isLoggedIn: (state) => !!state.token && !!state.user,
    isAdmin: (state) => state.user?.role === 'admin',
    isTeacher: (state) => state.user?.role === 'teacher',
    // 本地判断 token 是否已过期（按 JWT exp）；无法解析时视为未过期，交给服务端 401 兜底
    isTokenExpired: (state) => {
      if (!state.token) return false
      const exp = parseJwtExp(state.token)
      if (exp == null) return false
      return Date.now() / 1000 >= exp
    }
  },
  
  actions: {
    async checkAuth() {
      if (!this.token) return false
      
      try {
        const res = await authAPI.getMe()
        this.user = res.user
        localStorage.setItem('user', JSON.stringify(res.user))
        return true
      } catch (error) {
        this.logout()
        return false
      }
    },
    
    async login(username, password) {
      this.loading = true
      try {
        const res = await authAPI.login({ username, password })
        this.token = res.access_token
        this.user = res.user
        localStorage.setItem('token', res.access_token)
        localStorage.setItem('user', JSON.stringify(res.user))
        return { success: true }
      } catch (error) {
        return { success: false, error: error.response?.data?.error || '登录失败' }
      } finally {
        this.loading = false
      }
    },
    
    async register(data) {
      this.loading = true
      try {
        const res = await authAPI.register(data)
        return { success: true, data: res }
      } catch (error) {
        return { success: false, error: error.response?.data?.error || '注册失败' }
      } finally {
        this.loading = false
      }
    },
    
    logout() {
      this.user = null
      this.token = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    },
    
    async updateProfile(data) {
      try {
        const res = await authAPI.updateProfile(data)
        this.user = res.user
        localStorage.setItem('user', JSON.stringify(res.user))
        return { success: true }
      } catch (error) {
        return { success: false, error: error.response?.data?.error || '更新失败' }
      }
    },
    
    async changePassword(oldPassword, newPassword) {
      try {
        await authAPI.changePassword({ old_password: oldPassword, new_password: newPassword })
        return { success: true }
      } catch (error) {
        return { success: false, error: error.response?.data?.error || '修改失败' }
      }
    }
  }
})
