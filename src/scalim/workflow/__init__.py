"""`workflow` 框架/运行时层(稳定导入路径).

说明:
- 本包承载 `workflow` 的执行编排、资源/`ctx`/`artifacts` 管理与内置加载器.
- `src/scalim/workflow/**` 禁止反向依赖 `scalim.dsl/**`(由 `pytest` 门禁守护).
- 运行时需兼容 `Python 3.6`.
"""

# pragma: scalim-public-api tier1:70:scalim.workflow.loaders|workflow 内置 loader 的上下文与实现|在自定义 loader/运行器中复用

__all__ = ()
