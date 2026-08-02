"""向量存储领域包。

- contracts: VectorBackend 协议与共享类型
- chroma / qdrant: 后端实现
- legacy: 旧公开接口兼容层
- factory: 按配置创建后端与兼容单例

本包刻意不在 __init__ 里聚合导入具体后端，保持轻量 lazy 加载。
"""
