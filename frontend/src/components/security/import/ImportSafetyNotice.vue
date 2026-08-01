<template>
  <el-alert class="import-safety-notice" type="info" :closable="false" show-icon>
    <template #title>受控 GitHub 导入边界</template>
    <ul>
      <li>仅支持公开 GitHub 仓库，服务端会校验仓库地址。</li>
      <li>系统将固定到一个 Commit 后下载归档，不会执行 <code>git clone</code>。</li>
      <li>系统不会安装依赖、构建或执行仓库内的任何代码。</li>
    </ul>
  </el-alert>
</template>

<style scoped lang="scss">
.import-safety-notice :deep(.el-alert__content) { min-width: 0; }
.import-safety-notice ul { margin: 8px 0 0; padding-left: 20px; color: #486581; line-height: 1.7; }
.import-safety-notice code { padding: 1px 4px; border-radius: 4px; background: #e9f2f6; color: #243b53; }
</style>
