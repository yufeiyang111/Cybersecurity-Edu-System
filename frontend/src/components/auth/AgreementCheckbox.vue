<template>
  <div
    class="agreement-checkbox"
    :class="{ 'agreement-checkbox--error': !!error }"
  >
    <label class="agreement-checkbox__label">
      <input
        type="checkbox"
        class="agreement-checkbox__native"
        :checked="modelValue"
        @change="handleChange"
      />
      <span class="agreement-checkbox__box" aria-hidden="true">
        <svg
          v-if="modelValue"
          viewBox="0 0 24 24"
          fill="none"
        >
          <path
            d="M5 12l5 5 9-9"
            stroke="#ffffff"
            stroke-width="3"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </span>
      <span class="agreement-checkbox__text">
        我已阅读并同意
        <a
          class="agreement-checkbox__link"
          href="#"
          @click.prevent.stop
        >《用户协议》</a>
        及
        <a
          class="agreement-checkbox__link"
          href="#"
          @click.prevent.stop
        >《隐私政策》</a>
      </span>
    </label>
    <p v-if="error" class="agreement-checkbox__error" role="alert">{{ error }}</p>
  </div>
</template>

<script setup>
const props = defineProps({
  modelValue: { type: Boolean, default: false },
  error: { type: String, default: '' }
})

const emit = defineEmits(['update:modelValue'])

function handleChange(event) {
  emit('update:modelValue', event.target.checked)
}
</script>

<style lang="scss" scoped>
.agreement-checkbox {
  margin: 4px 0 20px;

  &__label {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    cursor: pointer;
  }

  &__native {
    position: absolute;
    width: 1px;
    height: 1px;
    opacity: 0;
    overflow: hidden;
    clip: rect(0 0 0 0);
  }

  &__box {
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    margin-top: 1px;
    border-radius: 5px;
    background: #ebf2fa;
    border: 1px solid transparent;
    transition: background 0.2s ease, border-color 0.2s ease;

    svg {
      width: 12px;
      height: 12px;
    }
  }

  &__label:hover .agreement-checkbox__box {
    border-color: #c8d4e3;
  }

  &__native:checked + .agreement-checkbox__box {
    background: #8d8d85;
    border-color: #8d8d85;
  }

  &__native:focus-visible + .agreement-checkbox__box {
    box-shadow: 0 0 0 3px rgba(141, 141, 133, 0.2);
  }

  &__text {
    font-size: 13px;
    color: #6b6b6b;
    line-height: 1.5;
  }

  &__link {
    color: #8d8d85;
    font-weight: 600;
    text-decoration: underline;
    text-underline-offset: 3px;

    &:hover {
      color: #1a1a1a;
    }
  }

  &__error {
    margin-top: 6px;
    font-size: 12px;
    color: #d0303a;
    line-height: 1.4;
  }

  &--error {
    .agreement-checkbox__box {
      background: #fdecec;
      border-color: #e6a1a6;
    }

    .agreement-checkbox__text {
      color: #d0303a;
    }
  }
}
</style>
