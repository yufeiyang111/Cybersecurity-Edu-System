<template>
  <BasePanel
    title="检索 Trace 查询"
    subtitle="按 Trace ID 查询单条脱敏阶段摘要；不会展示用户问题或候选正文。"
  >
    <form class="trace-form" @submit.prevent="submit">
      <label for="rag-trace-id">Trace ID</label>
      <div>
        <input
          id="rag-trace-id"
          v-model.trim="traceId"
          inputmode="numeric"
          maxlength="12"
          placeholder="例如 42"
        >
        <BaseButton variant="primary" type="submit" :disabled="loading">
          <BaseIcon name="search" :size="15" />
          <span>{{ loading ? '查询中' : '查询' }}</span>
        </BaseButton>
      </div>
      <p v-if="validationMessage" class="trace-form__error" role="alert">{{ validationMessage }}</p>
    </form>
  </BasePanel>
</template>

<script setup>
import { ref } from 'vue'
import { BaseButton, BaseIcon, BasePanel } from '@/components/ui'

defineProps({
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['load-trace'])
const traceId = ref('')
const validationMessage = ref('')

function submit() {
  const normalized = Number(traceId.value)
  if (!Number.isInteger(normalized) || normalized <= 0) {
    validationMessage.value = '请输入正整数 Trace ID。'
    return
  }
  validationMessage.value = ''
  emit('load-trace', normalized)
}
</script>

<style scoped lang="scss">
.trace-form {
  label,
  p {
    display: block;
  }

  label {
    margin-bottom: 6px;
    color: #475569;
    font-size: 12px;
    font-weight: 650;
  }

  > div {
    display: flex;
    gap: 8px;
  }

  input {
    min-width: 0;
    flex: 1;
    padding: 8px 10px;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    color: #0f172a;
    background: #ffffff;
    font: inherit;
    font-size: 13px;

    &:focus-visible {
      border-color: #2563eb;
      outline: 2px solid #bfdbfe;
      outline-offset: 1px;
    }
  }
}

.trace-form__error {
  margin: 6px 0 0;
  color: #b91c1c;
  font-size: 12px;
}

@media (min-width: 768px) and (max-width: 1200px) {
  .trace-form > div {
    gap: 7px;
  }
}

@media (max-width: 767px) {
  .trace-form > div {
    flex-direction: column;
  }
}
</style>
