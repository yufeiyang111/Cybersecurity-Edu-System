import { reactive, ref } from 'vue'

export function useAuthForm(initialValues = {}) {
  const form = reactive({ ...initialValues })
  const errors = reactive({})
  const submitting = ref(false)

  function setError(field, message) {
    errors[field] = message
  }

  function clearError(field) {
    delete errors[field]
  }

  function clearErrors() {
    for (const key of Object.keys(errors)) {
      delete errors[key]
    }
  }

  async function run(action) {
    if (submitting.value) return
    submitting.value = true
    try {
      await action()
    } finally {
      submitting.value = false
    }
  }

  return { form, errors, submitting, setError, clearError, clearErrors, run }
}
