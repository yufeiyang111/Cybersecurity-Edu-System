import { ref } from 'vue'
import { securityAPI } from '@/api'
import { securityApiErrorMessage } from '@/features/security/presentation'

export function useProjectImport() {
  const githubImportLoading = ref(false)
  const githubImportError = ref('')

  const resetGitHubImport = () => {
    githubImportError.value = ''
  }

  const importGitHubSnapshot = async (projectId, repositoryUrl) => {
    if (githubImportLoading.value) return null

    githubImportError.value = ''
    githubImportLoading.value = true
    try {
      return await securityAPI.importGitHubSnapshot(projectId, {
        repository_url: repositoryUrl.trim()
      })
    } catch (error) {
      githubImportError.value = securityApiErrorMessage(error, 'GitHub 导入失败，请检查仓库地址和访问限制。')
      return null
    } finally {
      githubImportLoading.value = false
    }
  }

  return {
    githubImportLoading,
    githubImportError,
    resetGitHubImport,
    importGitHubSnapshot
  }
}
