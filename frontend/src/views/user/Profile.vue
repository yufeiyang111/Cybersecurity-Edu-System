<template>
  <div class="profile-page">
    <ProfileTabs
      :questions="questions"
      :favorites="favorites"
    />

    <section class="profile-overview">
      <div class="profile-heatmaps">
        <ContributionHeatmap
          title="问答活跃"
          :events="qaEvents"
        />
        <ContributionHeatmap
          title="任务活跃"
          :events="taskEvents"
        />
      </div>
      <RecentActivityList class="profile-overview__item" />
    </section>

    <section id="security" class="profile-security">
      <div class="profile-security__header">
        <h3>安全设置</h3>
        <span class="profile-security__sub">第三方账号绑定</span>
      </div>
      <OAuthBindingCard />
    </section>

    <MemorySettingsCard />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import ProfileTabs from '@/components/user/ProfileTabs.vue'
import ContributionHeatmap from '@/components/user/ContributionHeatmap.vue'
import RecentActivityList from '@/components/user/RecentActivityList.vue'
import OAuthBindingCard from '@/components/user/OAuthBindingCard.vue'
import MemorySettingsCard from '@/components/user/MemorySettingsCard.vue'
import { useProfileStats } from '@/composables/user/useProfileStats'

const { questions, favorites, qaEvents, taskEvents, load } = useProfileStats()

onMounted(() => {
  load()
})
</script>

<style lang="scss" scoped>
@use '@/styles/user-vars' as *;

.profile-page {
  min-width: 0;
}

.profile-overview {
  display: flex;
  flex-direction: column;
  gap: 16px;

  &__item {
    margin-top: 0;
  }
}

.profile-heatmaps {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

@include respond-to('md') {
  .profile-heatmaps {
    grid-template-columns: 1fr;
  }
}

.profile-security {
  margin-top: 24px;
  scroll-margin-top: 16px;
}

.profile-security__header {
  margin-bottom: 12px;

  h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: $text-primary;
  }
}

.profile-security__sub {
  font-size: 12px;
  color: $text-secondary;
}
</style>
