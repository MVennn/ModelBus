2026-11-05 踩坑：仓根 .codegraph/ 存在，但 codegraph_status/codegraph_explore 报 `unable to open database file`、.codegraph/** 为空；按规则退回 grep/glob/read，未建索引。
2026-11-05 踩坑：并行会话重复写同名文件导致 tests/test_dsh_sync_retry_policy.py 的 CREDS 字面量未闭合（SyntaxError: unterminated string literal line 111）；改用三引号字符串。py_compile 写 tools/__pycache__ 触发 [WinError 5] 拒绝访问，验证命令统一加 python -B。
2026-11-05 踩坑：tempfile.TemporaryDirectory() 探测不到可用目录（FileNotFoundError: No usable temporary directory found），.work/*.txt 重定向触发 Permission denied；CLI 验证改用内存 stdout 捕获。
2026-11-05 踩坑：单测从 .work 静态夹具改为纯内存 VFS（mock Path.exists/read_text/write_text），断言 dry-run 零写入，消除外部文件与 %TEMP% 依赖；并发写同名文件曾触发 file changed since it was read，最终以最新落盘内容验收。
