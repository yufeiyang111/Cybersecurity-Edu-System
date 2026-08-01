<template>
  <div class="home-page">
    <!-- 顶部导航 -->
    <header class="home-header">
      <div class="container">
        <div class="header-content">
          <div class="logo" @click="$router.push('/')">
            <el-icon :size="32" color="#2ea44f"><Connection /></el-icon>
            <span class="logo-text">CyberGuard</span>
          </div>
          <nav class="nav-menu">
            <router-link to="/" class="nav-item">首页</router-link>
            <router-link to="/qa" class="nav-item">智能问答</router-link>
            <router-link to="/knowledge" class="nav-item">知识库</router-link>
            <router-link to="/graph" class="nav-item">知识图谱</router-link>
          </nav>
          <div class="header-actions">
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
              <el-button @click="$router.push('/login')">登录</el-button>
              <el-button type="primary" @click="$router.push('/register')">注册</el-button>
            </template>
          </div>
        </div>
      </div>
    </header>

    <!-- 英雄区域 -->
    <section class="hero-section">
      <div class="container">
        <div class="hero-content">
          <h1 class="hero-title">网络安全智能问答教学系统</h1>
          <p class="hero-desc">
            基于检索增强生成（RAG）与大语言模型（LLM）的智能问答平台，<br>
            为您提供精准、专业的网络安全知识解答
          </p>
          <div class="hero-actions">
            <el-button v-if="userStore.isLoggedIn" type="success" size="large" @click="$router.push('/security/projects')">
              <el-icon><Connection /></el-icon>
              安全工作台
            </el-button>
            <el-button type="primary" size="large" @click="$router.push('/qa')">
              <el-icon><ChatDotRound /></el-icon>
              开始提问
            </el-button>
            <el-button size="large" @click="$router.push('/knowledge')">
              <el-icon><Reading /></el-icon>
              浏览知识库
            </el-button>
          </div>
        </div>
        <div class="hero-visual">
          <div class="visual-card">
            <div class="visual-icon">
              <el-icon :size="48" color="#2ea44f"><Monitor /></el-icon>
            </div>
            <div class="visual-text">
              <span class="visual-label">AI智能助手</span>
              <span class="visual-desc">7×24小时在线解答</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 功能特性 -->
    <section class="features-section">
      <div class="container">
        <h2 class="section-title">核心功能</h2>
        <div class="features-grid">
          <div class="feature-card">
            <div class="feature-icon">
              <el-icon :size="40" color="#2ea44f"><ChatDotRound /></el-icon>
            </div>
            <h3>智能问答</h3>
            <p>基于RAG技术，融合向量检索与知识图谱，提供精准的专业答案</p>
          </div>
          <div class="feature-card">
            <div class="feature-icon">
              <el-icon :size="40" color="#2ea44f"><Document /></el-icon>
            </div>
            <h3>知识库管理</h3>
            <p>系统化的网络安全知识分类，支持多维度检索与浏览</p>
          </div>
          <div class="feature-card">
            <div class="feature-icon">
              <el-icon :size="40" color="#2ea44f"><Connection /></el-icon>
            </div>
            <h3>知识图谱</h3>
            <p>可视化展示知识点关联，支持多跳推理与关系探索</p>
          </div>
          <div class="feature-card">
            <div class="feature-icon">
              <el-icon :size="40" color="#2ea44f"><Clock /></el-icon>
            </div>
            <h3>学习历史</h3>
            <p>保存问答记录，支持收藏与回顾，让学习更连贯</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 热门知识 -->
    <section class="hot-section">
      <div class="container">
        <div class="section-header">
          <h2 class="section-title">热门知识</h2>
          <router-link to="/knowledge" class="more-link">
            查看更多 <el-icon><ArrowRight /></el-icon>
          </router-link>
        </div>
        <div class="hot-grid" v-loading="loading">
          <div
            v-for="item in hotItems"
            :key="item.id"
            class="hot-card"
            @click="$router.push(`/knowledge/${item.id}`)"
          >
            <div class="hot-tag">
              <el-tag size="small" type="info">{{ item.category_name }}</el-tag>
              <el-tag size="small" :type="getDifficultyType(item.difficulty)">
                {{ getDifficultyText(item.difficulty) }}
              </el-tag>
            </div>
            <h4 class="hot-title">{{ item.title }}</h4>
            <p class="hot-summary">{{ item.summary }}</p>
            <div class="hot-meta">
              <span><el-icon><View /></el-icon> {{ item.view_count }}</span>
              <span><el-icon><Star /></el-icon> {{ item.favorite_count }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 底部 -->
    <footer class="home-footer">
      <div class="container">
        <p>CyberGuard 网络安全智能问答教学系统 &copy; 2024</p>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { knowledgeAPI } from '@/api'
import { ElMessage } from 'element-plus'
import { Connection, Document, Clock, ArrowRight, View, Star, User, ChatDotRound, Setting, SwitchButton } from '@element-plus/icons-vue'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const hotItems = ref([])

const getDifficultyType = (difficulty) => {
  const types = { easy: 'success', medium: 'warning', hard: 'danger' }
  return types[difficulty] || 'info'
}

const getDifficultyText = (difficulty) => {
  const texts = { easy: '入门', medium: '进阶', hard: '高级' }
  return texts[difficulty] || '普通'
}

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
  loading.value = true
  try {
    const res = await knowledgeAPI.getHot({ limit: 8 })
    hotItems.value = res.items || []
  } catch (error) {
    console.error('获取热门知识失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchHotKnowledge()
})
</script>

<style lang="scss" scoped>
.home-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
}

// 头部
.home-header {
  background: #ffffff;
  border-bottom: 1px solid #d0d7de;
  position: sticky;
  top: 0;
  z-index: 100;
  
  .header-content {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 64px;
  }
  
  .logo {
    display: flex;
    align-items: center;
    cursor: pointer;
    
    .logo-text {
      margin-left: 8px;
      font-size: 20px;
      font-weight: 600;
      color: #24292f;
    }
  }
  
  .nav-menu {
    display: flex;
    gap: 32px;
    
    .nav-item {
      color: #57606a;
      font-size: 15px;
      transition: color 0.2s;
      text-decoration: none;
      
      &:hover, &.router-link-active {
        color: #2ea44f;
        text-decoration: none;
      }
    }
  }
  
  .header-actions {
    display: flex;
    align-items: center;
    gap: 12px;
    
    .user-info {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      
      .username {
        color: #57606a;
      }
    }
  }
}

// 英雄区域 - GitHub 风格深色主题
.hero-section {
  background: linear-gradient(180deg, #161b22 0%, #0d1117 100%);
  padding: 80px 0;
  color: #c9d1d9;
  
  .container {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  
  .hero-content {
    max-width: 600px;
    
    .hero-title {
      font-size: 42px;
      font-weight: 700;
      margin-bottom: 20px;
      line-height: 1.3;
      color: #f0f6fc;
    }
    
    .hero-desc {
      font-size: 18px;
      line-height: 1.8;
      color: #8b949e;
      margin-bottom: 32px;
    }
    
    .hero-actions {
      display: flex;
      gap: 16px;
      
      .el-button {
        padding: 12px 32px;
        font-size: 16px;
        border-radius: 6px;
        
        .el-icon {
          margin-right: 6px;
        }
      }
    }
  }
  
  .hero-visual {
    .visual-card {
      background: rgba(46, 164, 79, 0.1);
      border: 1px solid rgba(46, 164, 79, 0.3);
      border-radius: 12px;
      padding: 40px;
      display: flex;
      align-items: center;
      gap: 20px;
      
      .visual-icon {
        width: 80px;
        height: 80px;
        background: rgba(46, 164, 79, 0.15);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      
      .visual-text {
        display: flex;
        flex-direction: column;
        gap: 8px;
        
        .visual-label {
          font-size: 24px;
          font-weight: 600;
          color: #2ea44f;
        }
        
        .visual-desc {
          font-size: 16px;
          color: #8b949e;
        }
      }
    }
  }
}

// 功能特性
.features-section {
  padding: 80px 0;
  background: #f6f8fa;
  
  .section-title {
    text-align: center;
    font-size: 32px;
    font-weight: 600;
    color: #24292f;
    margin-bottom: 48px;
  }
  
  .features-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 24px;
    
    .feature-card {
      text-align: center;
      padding: 32px 24px;
      border-radius: 6px;
      background: #ffffff;
      border: 1px solid #d0d7de;
      transition: all 0.2s ease;
      
      &:hover {
        border-color: #2ea44f;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
      }
      
      .feature-icon {
        width: 72px;
        height: 72px;
        background: #f6f8fa;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 20px;
        border: 1px solid #d0d7de;
      }
      
      h3 {
        font-size: 18px;
        color: #24292f;
        margin-bottom: 12px;
        font-weight: 600;
      }
      
      p {
        color: #57606a;
        font-size: 14px;
        line-height: 1.6;
        margin: 0;
      }
    }
  }
}

// 热门知识
.hot-section {
  padding: 80px 0;
  background: #ffffff;
  
  .section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 32px;
    
    .section-title {
      font-size: 28px;
      font-weight: 600;
      color: #24292f;
      margin: 0;
    }
    
    .more-link {
      display: flex;
      align-items: center;
      gap: 4px;
      color: #2ea44f;
      font-size: 14px;
      text-decoration: none;
      
      &:hover {
        text-decoration: underline;
      }
    }
  }
  
  .hot-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 24px;
    
    .hot-card {
      background: #ffffff;
      border: 1px solid #d0d7de;
      border-radius: 6px;
      padding: 20px;
      cursor: pointer;
      transition: all 0.2s ease;
      
      &:hover {
        border-color: #2ea44f;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
      }
      
      .hot-tag {
        display: flex;
        gap: 8px;
        margin-bottom: 12px;
      }
      
      .hot-title {
        font-size: 16px;
        font-weight: 600;
        color: #24292f;
        margin-bottom: 8px;
        line-height: 1.4;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }
      
      .hot-summary {
        font-size: 13px;
        color: #57606a;
        line-height: 1.5;
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        overflow: hidden;
        margin-bottom: 12px;
      }
      
      .hot-meta {
        display: flex;
        gap: 16px;
        font-size: 12px;
        color: #8c959f;
        
        span {
          display: flex;
          align-items: center;
          gap: 4px;
        }
      }
    }
  }
}

// 底部
.home-footer {
  margin-top: auto;
  padding: 24px 0;
  background: #24292f;
  color: #8b949e;
  text-align: center;
  font-size: 14px;
  border-top: 1px solid #d0d7de;
  
  p {
    margin: 0;
  }
}

@media (max-width: 1024px) {
  .hero-section .container {
    flex-direction: column;
    text-align: center;
    
    .hero-content {
      max-width: 100%;
    }
    
    .hero-visual {
      margin-top: 40px;
    }
  }
  
  .features-grid,
  .hot-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .features-grid,
  .hot-grid {
    grid-template-columns: 1fr;
  }
  
  .nav-menu {
    display: none;
  }
}
</style>
