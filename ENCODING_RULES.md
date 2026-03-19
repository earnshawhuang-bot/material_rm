# 编码与乱码防护规范

## 1. 编码基线（统一约束）
- 仓库文本文件统一使用 `UTF-8`。
- 行结束符统一为 `LF`。
- 不允许出现 Unicode replacement character（`U+FFFD`）。

## 2. Windows / PowerShell 操作约束
- 建议每次开 PowerShell 5.1 先执行以下初始化（只影响当前会话）：
  ```powershell
  chcp 65001 > $null
  [Console]::InputEncoding  = [System.Text.UTF8Encoding]::new($false)
  [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
  $OutputEncoding           = [System.Text.UTF8Encoding]::new($false)
  ```
- 读取文件必须显式指定编码：`Get-Content <path> -Encoding UTF8`
- 写入文件必须显式指定编码：`Set-Content <path> -Encoding UTF8` 或 `Out-File -Encoding utf8`
- 禁止使用默认编码读写（PowerShell 5.1 默认行为会引发乱码风险）。

## 3. 改动流程（先检查后改动）
1. 修改前运行编码哨兵：`python scripts/check_encoding.py`
2. 仅在检查通过后开始业务改动。
3. 修改后再次运行编码哨兵，必须为 `OK`。

## 4. 文件损坏处置流程
1. 若发现源码/编辑器内出现乱码，先判定是否“文件真实损坏”。
2. 一旦确认损坏，先恢复该文件到基线版本，再重放业务改动。
3. 禁止在乱码文件上继续叠加修改。

## 5. 关键哨兵文件
- `backend/static/index.html`

该文件会被编码检查脚本做额外锚点校验，防止 UI 文案被静默破坏。
