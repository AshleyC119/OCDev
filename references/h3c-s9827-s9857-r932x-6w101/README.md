# H3C 开发参考手册

选择日期：2026-10-27。厂家 H3C 已由用户确认；本目录只补充公开官方参考材料。

主参考为《H3C S9827 & S9857系列交换机 命令参考-R932x-6W101》。官网导读明确说明介绍的是 **Release 9323** 所支持的命令；R932x 是发布系列，6W101 是资料版本，两者不要混同。

## 选择依据

样本 B 同时含 400GE、拆分形态的 200GE 接口，以及 S-MLAG、PFC、WRED/ECN、WFQ、缓冲区告警、INT、gRPC/MOD。选取面向高密度数据中心交换机的完整命令参考，比通用 Comware 入门手册更贴近本次任务。

尤其是：B 的 64 个原生 400GE 接口和 128 个带拆分后缀的 200GE 接口，符合 128 个物理端口中一部分拆成两个 200GE 的形态。官网介绍的 S9827-128DH 提供 128 个 400G 端口，因而是合理候选，但这不足以确认样本机型。

对下列代表性语法已在同一套官方资料中核查，不代表整份 CLI 已逐条验证：

| B 中的命令特征 | 官方章节 |
| --- | --- |
| `FourHundredGigE` / `TwoHundredGigE` 接口 | 03 接口管理／以太网接口 |
| `link-aggregation mode dynamic`、`port s-mlag group` | 04 二层技术／以太网链路聚合 |
| `priority-flow-control poolid … headroom …` | 04 二层技术／PFC |
| `qos wred queue … low-limit … high-limit … ecn` | 10 ACL和QoS／QoS |
| `qos wfq … group 1 byte-count …` | 10 ACL和QoS／QoS |
| `buffer egress cell queue …`、Headroom 告警 | 10 ACL和QoS／数据缓冲区 |
| `telemetry ifa global enable`、`telemetry ifa role transit` | 16 Telemetry／INT |
| gRPC、Flow Group、MOD | 16 Telemetry 下相应章节 |

## 文件和使用

- `H3C_S9827_S9857_Command_Reference_R932x_6W101.pdf`：官方整本 PDF，保留下载原字节。
- `manual.txt`：从 PDF 提取的 UTF-8 检索文本，`=== PDF PAGE n ===` 表示从 1 开始的物理 PDF 页码。文字抽取可能损失表格、空格和命令加粗／斜体信息，歧义处回看 PDF 或官网。
- `command-links.json`：从官网命令总索引抽取的命令名称和章节 URL，便于定位；不是人工编译的翻译规则。
- `manual-guide.html`、`command-index.html`：官网导读和总索引的原始网页快照。
- `download.json`、`web-snapshots.json`、`inventory.json`：来源、下载日期及本地文件校验信息。

开发时按需检索命令的语法、视图、单位、取值和默认值；无需将整本手册一次性塞入模型上下文。不把官方举例中的固定参数当成样本 OC 的缺失值。

## 适用边界

这是当前信息下选择的一套匹配度较高的开发参考，**不是已核实的原设备手册**。样本没有版本横幅，OC 也未给出明确机型／版本字段；设备实际是否属于 S9827/S9857，以及是否运行 Release 9323，均待来源方确认。

用户确认 H3C 不等于确认 Comware 的具体大版本。手册语法与样本冲突时，记录冲突和不确定项，不将样本自动改写成手册示例。后续拿到真实机型和 `display version` 信息，再核对对应手册；若在代码冻结后更换资料或实现，应另记版本。

## 官方来源

- [手册主页](https://www.h3c.com/cn/Service/Document_Software/Document_Center/Home/Switches/00-Public/Command/Command_Manual/H3C_S9827_CR-20807/)
- [命令参考导读：Release 9323](https://www.h3c.com/cn/Service/Document_Software/Document_Center/Home/Switches/00-Public/Command/Command_Manual/H3C_S9827_CR-20807/00/)
- [命令总索引及整本下载入口](https://www.h3c.com/cn/Service/Document_Software/Document_Center/Home/Switches/00-Public/Command/Command_Manual/H3C_S9827_CR-20807/99/)
- [H3C 官方整本 PDF 下载](https://download.h3c.com/app/cn/download.do?id=14180096)
- [S9827 系列产品介绍](https://www.h3c.com/cn/Products_And_Solution/InterConnect/Products/Switches/Products/Data_Center_Switch/Aggregation_Switch/S9800/S9827/)
- [以太网接口命令](https://www.h3c.com/cn/d_202506/2571116_30005_0.htm)
- [以太网链路聚合命令](https://www.h3c.com/cn/d_202506/2571122_30005_0.htm)
- [PFC 命令](https://www.h3c.com/cn/d_202506/2571129_30005_0.htm)
- [QoS 命令](https://www.h3c.com/cn/d_202506/2571178_30005_0.htm)
- [数据缓冲区命令](https://www.h3c.com/cn/d_202506/2571179_30005_0.htm)
- [INT 命令](https://www.h3c.com/cn/d_202506/2571236_30005_0.htm)
