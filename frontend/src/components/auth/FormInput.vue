<template>
  <div class="form-input" :class="{ 'form-input--error': !!error }">
    <label v-if="label || $slots.label" class="form-input__label" :for="inputId">
      <slot name="label">{{ label }}</slot>
    </label>

    <div class="form-input__control">
      <input
        :id="inputId"
        class="form-input__field"
        :type="type"
        :placeholder="placeholder"
        :value="modelValue"
        :autocomplete="autocomplete"
        :name="name"
        @input="handleInput"
        @blur="emit('blur')"
      />
      <div v-if="$slots.suffix" class="form-input__suffix">
        <slot name="suffix" />
      </div>
    </div>

    <p v-if="error" class="form-input__error" role="alert">{{ error }}</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: { type: String, default: '' },
  type: { type: String, default: 'text' },
  placeholder: { type: String, default: '' },
  modelValue: { type: String, default: '' },
  error: { type: String, default: '' },
  autocomplete: { type: String, default: 'off' },
  name: { type: String, default: '' }
})

const emit = defineEmits(['update:modelValue', 'blur'])

const inputId = computed(() => `auth-input-${Math.random().toString(36).slice(2, 10)}`)

function handleInput(event) {
  emit('update:modelValue', event.target.value)
}
</script>

<style lang="scss" scoped>
.form-input {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 20px;

  &__label {
    display: block;
    font-size: 13px;
    font-weight: 600;
    color: #1a1a1a;
    letter-spacing: 0.01em;
  }

  &__control {
    position: relative;
  }

  &__field {
    width: 100%;
    padding: 14px 16px;
    font-size: 15px;
    font-family: inherit;
    color: #1a1a1a;
    background: #ebf2fa;
    border: 1px solid transparent;
    border-radius: 14px;
    outline: none;
    transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;

    &::placeholder {
      color: #9aa7b8;
    }

    &:hover {
      border-color: #d4dfee;
    }

    &:focus {
      border-color: #8d8d85;
      background: #ffffff;
      box-shadow: 0 0 0 3px rgba(141, 141, 133, 0.12);
    }
  }

  &__suffix {
    position: absolute;
    top: 50%;
    right: 12px;
    transform: translateY(-50%);
    display: flex;
    align-items: center;
  }

  &__error {
    font-size: 12px;
    color: #d0303a;
    line-height: 1.4;
  }

  &--error {
    .form-input__field {
      background: #fdecec;
      border-color: #e6a1a6;

      &:focus {
        border-color: #d0303a;
        box-shadow: 0 0 0 3px rgba(208, 48, 58, 0.12);
      }
    }
  }
}
</style>
