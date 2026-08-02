import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

export function useAvatarUpload() {
  const uploading = ref(false)
  const userStore = useUserStore()

  const beforeUpload = (file) => {
    const isImage = file.type.startsWith('image/')
    const isLt2M = file.size / 1024 / 1024 < 2

    if (!isImage) {
      ElMessage.error('只能上传图片文件')
      return false
    }
    if (!isLt2M) {
      ElMessage.error('图片大小不能超过 2MB')
      return false
    }
    return true
  }

  const uploadHandler = ({ file }) => {
    return new Promise((resolve) => {
      const reader = new FileReader()
      reader.onload = async (e) => {
        const avatarUrl = e.target.result
        uploading.value = true
        const result = await userStore.updateProfile({
          email: userStore.user?.email || '',
          nickname: userStore.user?.nickname || '',
          avatar_url: avatarUrl
        })
        uploading.value = false

        if (result.success) {
          ElMessage.success('头像更新成功')
        } else {
          ElMessage.error(result.error || '头像更新失败')
        }
        resolve()
      }
      reader.readAsDataURL(file)
    })
  }

  return { uploading, beforeUpload, uploadHandler }
}
