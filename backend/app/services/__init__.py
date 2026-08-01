"""CyberGuard 服务包。

请从具体领域模块导入服务，例如：
`from app.services.source_intake import validate_and_extract_zip`。

这里故意不聚合导入 RAG、向量、图谱或嵌入实现，避免轻量扫描、上传和测试
因可选 AI 依赖产生启动开销或导入副作用。
"""

__all__: tuple[str, ...] = ()
