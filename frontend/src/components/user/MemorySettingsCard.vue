<template>
  <section class="memory-settings">
    <div class="memory-settings__header">
      <h3>持久记忆</h3>
      <span class="memory-settings__sub">记住你在问答中透露的偏好与背景，跨会话生效</span>
    </div>

    <div class="memory-settings__row">
      <div class="memory-settings__info">
        <strong>全局持久记忆</strong>
        <p>开启后，系统会从你的问答中提取偏好、背景等事实并长期保留，回答时自动参考；可在「我的记忆」中查看和删除。</p>
      </div>
      <label class="switch">
        <input
          type="checkbox"
          :checked="enabled"
          :disabled="saving"
          @change="onToggle"
        >
        <span class="switch__slider" />
      </label>
    </div>

    <div class="memory-settings__actions">
      <RouterLink class="memory-settings__link" to="/user/memories">
        查看我的记忆
      </RouterLink>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { authAPI } from '@/api'

const enabled = ref(false)
const saving = ref(false)

const load = async () => {
  try {
    const res = await authAPI.getPreferences()
    enabled.value = Boolean(res?.preferences?.persistent_memory_enabled ?? res?.persistent_memory_enabled)
  } catch (e) {
    /* 忽略加载失败 */
  }
}

const onToggle = async (event) => {
  const next = event.target.checked
  saving.value = true
  try {
    await authAPI.updatePreferences({ persistent_memory_enabled: next })
    enabled.value = next
  } catch (e) {
    enabled.value = !next
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style lang="scss" scoped>
.memory-settings {
  margin-top: 24px;
  scroll-margin-top: 16px;
}

.memory-settings__header {
  margin-bottom: 12px;

  h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: #0f172a;
  }
}

.memory-settings__sub {
  font-size: 12px;
  color: #64748b;
}

.memory-settings__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
}

.memory-settings__info {
  strong {
    color: #0f172a;
    font-size: 14px;
  }

  p {
    margin: 6px 0 0;
    color: #64748b;
    font-size: 12px;
    line-height: 1.6;
  }
}

.memory-settings__actions {
  margin-top: 12px;
}

.memory-settings__link {
  color: #2563eb;
  font-size: 13px;
  text-decoration: none;

  &:hover {
    text-decoration: underline;
  }
}

.switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
  flex-shrink: 0;

  input {
    opacity: 0;
    width: 0;
    height: 0;
  }

  &__slider {
    position: absolute;
    inset: 0;
    border-radius: 999px;
    background: #cbd5e1;
    transition: background 0.3s ease;

    &::before {
      content: '';
      position: absolute;
      width: 18px;
      height: 18px;
      left: 3px;
      top: 3px;
      border-radius: 50%;
      background: #fff;
      transition: transform 0.3s ease;
    }
  }

  input:checked + &__slider {
    background: #2563eb;
  }

  input:checked + &__slider::before {
    transform: translateX(20px);
  }

  input:disabled + &__slider {
    opacity: 0.6;
  }
}
</style>
