# 开发记录与冻结身份（Development Notes）

## 1. 任务与材料

- 目标：把完整 OC JSON 文档离线、确定性地翻译为 H3C CLI，覆盖尽可能多的输入，并结构化报告未支持/歧义/异常项。
- 唯一开发配置材料：`data/raw/` 中的样本 B（OC JSON + 配对原生 CLI）。原始文件字节自始至终未改动；`python scripts/verify_materials.py` 可复核 `data/manifest.json` 中的 SHA256。
- 厂家 H3C 由用户于 2026-10-27 确认。样本真实型号/Comware 版本/配对快照关系未确认（见 `docs/LIMITATIONS.md`）。
- 开发参考：`references/h3c-s9827-s9857-r932x-6w101/`，主参考为《H3C S9827 & S9857 系列交换机 命令参考-R932x-6W101》（R932x 发布系列 / 6W101 资料版本；导读明确对应 Release 9323）。使用方式：先读该目录 `README.md`，按需检索 `manual.txt`（保留 PDF 物理页码标记）、`command-links.json`、官网快照；PDF 原字节保留。
- 官方来源记录在该目录 README 的链接列表；本次未引入任何第三方实现、其他工作区或额外配置样本。

## 2. 开发过程与检查

1. **材料校验**：`python scripts/verify_materials.py` → OC SHA256 `b60b07a2…f430`（931,414 bytes）、CLI SHA256 `53abe733…4215`（445,120 bytes），均与清单一致。
2. **结构逆向**：从 OC 逐节抽取字段、实例与取值语义；从配对 CLI 重建 1183 个 `system-view` 分段，得到每一段的准确命令行、顺序与空白风格。映射逐段实现，以"与参考逐字节一致"为开发目标（仅开发期使用参考文本，运行时不读取）。
3. **分段对拍**：`tools/compare_segments.py <段号或区间>` 对每个特性段做字节级比对。最终所有 1183 段中 1182 段逐字节一致，唯一差异见 `docs/LIMITATIONS.md` 第 1 节（4 行的 dot1p-lp 固定缺省表，OC 无来源）。
4. **整体对拍**：`tools/compare.py` → 生成 15517 行，参考 15521 行；仅 1 个差异块（上述 4 行 insert），无多余行。
5. **覆盖率审计**：翻译器对每个数据叶子追踪"已消费/已忽略/未映射"。样本 B 共 26,341 个数据叶子：16,562 个由映射消费，7,012 个为重复元数据（仅重复父键/索引），2,767 个为未映射内容；后者按路径模板在报告中逐项列出（`unmapped` / `coverage.missing`）。
6. **确定性**：连续两次运行输出 SHA256 相同（`ff9752bc…75cf`）。
7. **离线约束测试**：源码中不出现参考 CLI 文件名/中文名，不导入网络或模型库（见 `tests/test_translator.py`）。
8. **回归测试**：`python -m unittest discover -s tests` → 12 项全部通过（含材料哈希、确定性、开发保真度、报告结构、空文档、非法输入、删减子系统不崩溃）。
9. **参数化冒烟检查**：对样本 B 做值替换后重译（主机名、ACL 源网段、trunk VLAN 列表、接口速率、BGP AS/router-id、device-id、sFlow collector、LLDP 管理地址、删除 qos 等），输出相应变化且无异常；逐节删除各顶层子树的压力测试无崩溃，仅产生可解释的 `error` 报告。
10. **未做**：未在真实 H3C 设备/模拟器上执行整篇脚本（见限制第 7 节）；未寻求额外测试材料。

## 3. 运行命令

```powershell
python -m oc2h3c data/raw/CQ-JLDC-2201-A03-H9867-GPULA-024.txt -o outputs/sampleB.cli --report outputs/sampleB.report.json --report-text outputs/sampleB.report.txt
```

仅 Python 3.8+ 标准库；离线；同输入同输出。退出码 0 正常、2 输入不可用。

## 4. 代码结构与实现身份

- 29 个 Python 模块、约 3,800 行（含注释/docstring），位于 `oc2h3c/`：
  - 核心：`loader.py`（读取/校验 JSON）、`context.py`（文档访问、覆盖率追踪、报告接口）、`emitter.py`（CLI 块渲染）、`pipeline.py`（固定顺序的映射流水线）、`report.py`（结构化报告与聚合）、`__main__.py`（CLI）。
  - 映射：`sections/` 下 20 个特性模块，顺序由 `sections/__init__.py` 的 `STEPS` 固定（该顺序是冻结身份的一部分）。
- 开发工具（不属于运行时）：`tools/compare.py`（整体对拍）、`tools/compare_segments.py`（分段对拍）；`tests/` 为回归测试。
- 文档：`docs/USAGE.md`、`docs/SUPPORT.md`、`docs/LIMITATIONS.md`、本文件；冻结清单 `FROZEN.json`。

## 5. 版本与冻结

- 实现版本：`oc2h3c 1.0.0`（`oc2h3c/__init__.py`）。
- 冻结日期：2026-10-27（Asia/Shanghai）。
- 冻结身份：`FROZEN.json` 记录 `oc2h3c/`、`tests/`、`tools/`、`docs/`、`README.md` 中每个文件的 SHA256 与字节数，以及输入材料哈希、样本 B 验证结果摘要。修改任何实现/文档后应重新生成并升级版本号。
- 复核方式：

```powershell
python -c "import json,hashlib,os; d=json.load(open('FROZEN.json',encoding='utf-8')); bad=[p for p,v in d['files'].items() if hashlib.sha256(open(p,'rb').read()).hexdigest()!=v['sha256']]; print('mismatches:',bad)"
```

## 6. 后续独立评测提示

- 评测输入应为同类的完整 OC 文档；翻译器不依赖样本 B 的设备名、路径或哈希，运行时也不读取参考 CLI 或参考手册。
- 由于目标设备型号/版本未确认，若评测方提供真实机型与 `display version`，应据此核对命令参考版本后再冻结新版本；当前冻结身份对应本目录材料与 `references/` 中的 Release 9323 开发参考。
