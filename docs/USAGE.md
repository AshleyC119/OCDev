# oc2h3c — OC → H3C CLI 翻译器

本目录是一次独立构建实验的交付物：把完整的 OpenConfig 风格 JSON（OC）文档参数化地、离线且确定性地翻译为 H3C（Comware）CLI 配置脚本，并对未支持、歧义、异常输入输出结构化报告。

## 单条使用命令

```powershell
python -m oc2h3c data/raw/CQ-JLDC-2201-A03-H9867-GPULA-024.txt -o outputs/sampleB.cli --report outputs/sampleB.report.json --report-text outputs/sampleB.report.txt
```

- 输入：一个完整 OC JSON 文档（单个 JSON 对象，UTF-8）。
- `-o`：生成的 H3C CLI 脚本（省略则写 stdout）。
- `--report` / `--report-text`：结构化 JSON 报告 / 人类可读报告（可选）。
- 运行时不联网、不调用模型、不读取任何参考 CLI 文本；同一输入产生逐字节相同的输出。
- Python 3.8+，仅标准库，无第三方依赖。

退出码：`0` 正常；`2` 输入不可用（空文件、非 UTF-8、非法 JSON、顶层非对象）。

## 交付内容

| 路径 | 说明 |
| --- | --- |
| `oc2h3c/` | 翻译器源码（`python -m oc2h3c`） |
| `tests/` | 回归测试（样本 B、确定性、离线约束、报告结构等） |
| `tools/compare.py` | 开发用整体对拍工具（仅开发期使用，运行时不使用） |
| `tools/compare_segments.py` | 开发用分段对拍工具 |
| `docs/SUPPORT.md` | 支持范围（逐段映射来源） |
| `docs/LIMITATIONS.md` | 已知限制、歧义与未支持项 |
| `docs/DEV_NOTES.md` | 开发检查、资料来源、版本与冻结身份 |
| `FROZEN.json` | 冻结版本的源码校验和与冻结信息 |
| `outputs/` | 开发验证产物（样本 B 生成结果与报告） |

## 开发验证摘要

对样本 B 的配对 CLI 参考逐字节对拍，15521 行中只有 `qos map-table dot1p-lp` 的 4 行无法由 OC 推导（详见 `docs/LIMITATIONS.md`）。其余全部一致。覆盖统计、未支持/歧义条目见 `outputs/sampleB.report.txt`。

## 材料与边界

- 唯一开发配置材料是 `data/raw/` 中的一份完整 OC 与配对 CLI；原始文件字节未改动（哈希见 `data/manifest.json`，可用 `python scripts/verify_materials.py` 校验）。
- 厂家已确认为 H3C；参考手册为 `references/h3c-s9827-s9857-r932x-6w101/`（R932x / 6W101，导读对应 Release 9323），按样本特征选作开发参考，**不代表已确认样本设备的真实型号/软件版本**。
- 配对 CLI 未经确认与 OC 同一时点、完全无损；翻译结果以结构化报告暴露不确定性，不静默丢弃输入。
