# OCDev 源码分享

本仓库分享 `oc2h3c 1.0.0`：使用完整样本 B 开发的静态 OC 风格 JSON → H3C CLI 翻译器。构建结果、支持范围和限制见 [README.md](README.md) 与 [docs/](docs/USAGE.md)。

## 克隆和运行

需要 Python 3.8+；运行时仅使用标准库，无需安装第三方依赖。

```sh
git clone https://github.com/AshleyC119/OCDev.git
cd OCDev
python scripts/verify_materials.py
python -m oc2h3c data/raw/CQ-JLDC-2201-A03-H9867-GPULA-024.txt -o outputs/sampleB.cli --report outputs/sampleB.report.json --report-text outputs/sampleB.report.txt
python -m unittest discover -s tests
```

`data/raw/` 包含开发样本 B 的原始 OC 和配对 CLI，便于直接复现开发验证。翻译器运行时只读取传入的 OC；配对 CLI 供开发测试与对拍工具使用。

## 冻结身份

源码、原始说明和 `FROZEN.json` 按开发交付的原字节复制，未按测试样本 A 修补。原冻结清单 SHA256 为：

```
7c3eff6441253e462ca4b2780b228fcf107487ac63f8e2575ddaac37d0cc85c1
```

本次分享新增的 Git 配置、此说明和校验脚本不改变原冻结的 40 个文件。可运行：

```sh
python scripts/verify_frozen.py
```

不要运行 `tools/freeze.py` 来替代校验；该工具会重写冻结记录。

## 官方手册

选用《H3C S9827 & S9857 系列交换机 命令参考-R932x-6W101》，导读对应 Release 9323。它是开发参考，原设备的真实型号和运行版本尚未确认。

仓库保留[资料说明和官网链接](references/h3c-s9827-s9857-r932x-6w101/README.md)、官方命令索引 `command-links.json` 和下载来源记录 `download.json`。资料说明中列出的 PDF、提取全文、网页快照和完整资料清单属于原本地归档，未随本次源码分享上传；需要时从官网获取。翻译器和测试运行均不依赖这些大文件。

## 验证范围

开发样本 B 的 12 项测试用于开发回归，不代表未知配置全部正确。首次 A 整文件测试已发现 ACL、前缀列表、BGP graceful-restart 和 VTY 超时的缺失；本仓库保留该次测试的原始受测版本。详见已有的支持范围和限制说明，生成脚本未在真实 H3C 设备上整篇验证。
