<template>
  <FormInput
    class="password-input"
    :label="label"
    :type="visible ? 'text' : 'password'"
    :placeholder="placeholder"
    :model-value="modelValue"
    :error="error"
    :autocomplete="autocomplete"
    @update:model-value="emit('update:modelValue', $event)"
    @blur="emit('blur')"
  >
    <template #label>
      <span class="password-input__head">
        <span>{{ label }}</span>
        <a
          v-if="showForgot"
          class="password-input__forgot"
          href="#"
          @click.prevent="emit('forgot')"
        >
          {{ forgotLabel }}
        </a>
      </span>
    </template>

    <template #suffix>
      <button
        type="button"
        class="password-input__toggle"
        :aria-label="visible ? '隐藏密码' : '显示密码'"
        :title="visible ? '隐藏密码' : '显示密码'"
        @click="visible = !visible"
      >
        <svg
          v-if="visible"
          class="password-input__eye"
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linejoin="round"
          />
          <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.8" />
        </svg>
        <svg
          v-else
          class="password-input__eye"
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M3 3l18 18"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
          />
          <path
            d="M10.7 5.1A10.7 10.7 0 0 1 12 5c6.5 0 10 7 10 7a17.6 17.6 0 0 1-3.1 4M6.6 6.6A17.4 17.4 0 0 0 2 12s3.5 7 10 7c1.7 0 3.2-.4 4.5-.9M9.9 9.9a3 3 0 0 0 4.2 4.2"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </button>
    </template>
  </FormInput>
</template>

<script setup>
import { ref } from 'vue'
import FormInput from './FormInput.vue'

defineProps({
  label: { type: String, default: '密码' },
  placeholder: { type: String, default: '' },
  modelValue: { type: String, default: '' },
  error: { type: String, default: '' },
  autocomplete: { type: String, default: 'current-password' },
  showForgot: { type: Boolean, default: false },
  forgotLabel: { type: String, default: '忘记密码？' }
})

const emit = defineEmits(['update:modelValue', 'blur', 'forgot'])

const visible = ref(false)
</script>

<style lang="scss" scoped>
.password-input {
  &__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
  }

  &__forgot {
    font-size: 12px;
    font-weight: 500;
    color: #8d8d85;
    text-decoration: underline;
    text-underline-offset: 3px;

    &:hover {
      color: #1a1a1a;
    }
  }

  &__toggle {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 6px;
    border: none;
    background: transparent;
    color: #8f9bad;
    cursor: pointer;
    border-radius: 8px;
    transition: color 0.2s ease, background 0.2s ease;

    &:hover {
      color: #1a1a1a;
      background: rgba(141, 141, 133, 0.1);
    }
  }

  &__eye {
    width: 18px;
    height: 18px;
    display: block;
  }
}
</style>
