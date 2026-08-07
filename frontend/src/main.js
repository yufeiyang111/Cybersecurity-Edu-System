import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import './styles/global.scss'
import './styles/chat-tokens.scss'
import './styles/markdown-code.scss'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
