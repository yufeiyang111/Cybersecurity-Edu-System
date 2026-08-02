<template>
  <aside class="profile-sidebar">
    <UserAvatarCard />
    <UserStatsCard
      class="sidebar-card"
      :questions="questions"
      :favorites="favorites"
      :answers="answers"
      :loading="loading"
    />
    <UserInfoCard class="sidebar-card" />
    <UserActionsCard class="sidebar-card" @save="editVisible = true" @password="passwordVisible = true" />

    <EditProfileDialog v-model="editVisible" />
    <ChangePasswordDialog v-model="passwordVisible" />
  </aside>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import UserAvatarCard from '@/components/user/UserAvatarCard.vue'
import UserStatsCard from '@/components/user/UserStatsCard.vue'
import UserInfoCard from '@/components/user/UserInfoCard.vue'
import UserActionsCard from '@/components/user/UserActionsCard.vue'
import EditProfileDialog from '@/components/user/EditProfileDialog.vue'
import ChangePasswordDialog from '@/components/user/ChangePasswordDialog.vue'
import { useProfileStats } from '@/composables/user/useProfileStats'

const userStore = useUserStore()

const editVisible = ref(false)
const passwordVisible = ref(false)

const { loading, questions, favorites, answers, load } = useProfileStats()

onMounted(() => {
  load()
})
</script>

<style lang="scss" scoped>
@use '@/styles/user-vars' as *;

.profile-sidebar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: $sidebar-width;
  flex-shrink: 0;
}

.sidebar-card {
  width: 100%;
}

@include respond-to('lg') {
  .profile-sidebar {
    width: 100%;
    max-width: 400px;
    margin: 0 auto;
  }
}
</style>
