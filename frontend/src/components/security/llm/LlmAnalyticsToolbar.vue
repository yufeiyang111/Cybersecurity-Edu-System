<template>
  <div class="analytics-toolbar"><div class="tabs"><button class="tab active">模型调用分析</button><button class="tab">分流</button></div></div>
</template>

<style scoped lang="scss">
.analytics-toolbar{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:16px}.tabs{display:flex;gap:22px;border-bottom:1px solid #e2e8f0}.tab{position:relative;padding:0 0 10px;border:0;background:transparent;color:#475569;font-size:14px}.tab.active{color:#2563eb;font-weight:600}.tab.active::after{content:"";position:absolute;right:0;bottom:-1px;left:0;height:2px;background:#2563eb}
</style>
