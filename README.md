# OCDevB

创建日期：2026-10-26。本目录用于一次仅使用开发样本 B 的独立 OC→CLI 翻译器构建实验。

## 材料

- `data/raw/CQ-JLDC-2201-A03-H9867-GPULA-024.txt`：完整开发输入，单行 JSON，含供应方导出约定。
- `data/raw/配置文本_CQ-JLDC-2201-A03-H9867-GPULA-024.txt`：对应原生 CLI 参考文本；用户于 2026-10-27 确认厂家为 H3C，具体机型和软件版本尚未确认。
- `data/manifest.json`：文件身份、大小及 SHA256。两份文件已按原字节复制并核验。
- `PROMPT.md`：可直接交给新 Agent 的任务提示词。
- `AGENTS.md`：本次独立构建实验的材料范围及实现约定。
- `references/h3c-s9827-s9857-r932x-6w101/`：H3C 官方整本命令参考及检索材料；参考范围为 S9827／S9857、R932x、资料版本 6W101，导读明确介绍 Release 9323。选择依据和适用边界见该目录的 `README.md`。

参考文本尚未经确认是同一时点、完全无损的标准答案。无法由 OC 确定的内容应记录歧义，避免从参考文本中直接补造未知输入的值。

## 开始

在此目录新建一个不继承既有项目对话的 Agent 会话，让它读取并执行 `PROMPT.md`。本目录只提供一个完整开发样本，没有其他配置样本或既有翻译器代码。

校验材料：

```powershell
python scripts/verify_materials.py
```

## 交付（本实验成果）

本工作区已完成一版静态 OC→H3C CLI 翻译器，源码在 `oc2h3c/`，使用方式与验证摘要见 `docs/USAGE.md`：

```powershell
python -m oc2h3c data/raw/CQ-JLDC-2201-A03-H9867-GPULA-024.txt -o outputs/sampleB.cli --report outputs/sampleB.report.json
```

支持范围见 `docs/SUPPORT.md`，已知限制与歧义见 `docs/LIMITATIONS.md`，开发检查、资料来源与冻结身份见 `docs/DEV_NOTES.md` / `FROZEN.json`。

开发完成后保存代码版本、使用的通用资料和运行命令，冻结该版本以供后续独立评测。

