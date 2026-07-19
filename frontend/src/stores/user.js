import { defineStore } from 'pinia'
import { authAPI } from '@/api'

export const useUserStore = defineStore('user', {
  state: () => ({
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    token: localStorage.getItem('token') || null,
    loading: false
  }),
  
  getters: {
    isLoggedIn: (state) => !!state.token && !!state.user,
    isAdmin: (state) => state.user?.role === 'admin',
    isTeacher: (state) => state.user?.role === 'teacher'
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
