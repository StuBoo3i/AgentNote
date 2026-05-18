# context_pack_common.py 修改说明

## 2026-05-18 19:47 CST

- 新增 `context_pack_common.py`。
- 收纳 Context Pack 子模块共用的通用 helper：
  - normalize / tokenize
  - quoted value 提取
  - profile table/column 访问
  - qualified source 提取
  - missing / scalar / dedupe
- 目的是真正删除 `context_pack.py` 底部的重复工具函数，而不是保留副本。
