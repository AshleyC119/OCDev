# 已知限制与歧义（Limitations）

本文件记录当前冻结版本的已知差距。凡 OC 中存在而 CLI 未表达的内容，报告都会以 `unsupported` / `ignored` / `unmapped` 形式显式列出，不会静默丢弃。

## 1. 与开发参考逐字节比对的唯一差异

样本 B 的配对参考共 15521 行；本实现生成 15517 行。逐段（1183 段）比对：1182 段逐字节一致，只有第 10 段缺少 4 行：

```
qos map-table dot1p-lp
import 0 export 0
import 1 export 1
import 2 export 2
```

OC 文档中没有任何 dot1p→local-priority 映射数据（文档中甚至不出现 `dot1p`/`map-table` 字样），这 4 行无法由输入推导，看起来是原参考生成器写死的缺省表。为遵守"不得回放参考文本、不得把参考中的固定内容当输入"的约束，本实现不输出这 4 行，并在报告中记为：

- `unsupported`：`qos/scheduler-policies`，说明参考输出的 dot1p-lp 缺省项在 OC 中无来源。

若后续确认该缺省表属于目标设备的固定默认配置，可按第 12 节的"固定常量"机制补入。

## 2. 固定常量/固定模板（OC 无法表达，报告中均记为 `ambiguous`）

- 登录 banner（`header login %` 及三行文本，含前导空格）：OC 中无 banner 文本，按参考模板固定输出。
- sFlow collector 描述 `netserver`：OC collector 无 description 字段。
- `telemetry apply flow-group system-defined ip`：OC 无 flow-group 定义。
- `priority-flow-control deadlock precision high`：OC 无对应属性。
- 口令存储关键字 `simple`（local-user / ssh / BGP peer password）。
- WRED/队列的 `ecn`、`qos wfq byte-count`、`group 1`、`group sp` 等命令形态关键字。
- `lldp ignore-pvid-inconsistency`、`line aux`/`line vty`、`telemetry ifa role transit` 等命令关键字。
- 参考文本中的交互应答行 `Y`（`port link-mode ...`、`peer ... enable`、`peer ... next-hop-local` 之后）按参考位置输出。
- 参考文本的空白风格（前导空格、双空格、行尾空格）被逐字节复现，以保证与参考脚本的文本一致性；这不影响 H3C 解析。

## 3. 编号与顺序策略（OC 无编号，报告中记为 `ambiguous`）

- **ACL 编号**：OC 只给名称与类型。基本 ACL（`ACL_CTRL`）按文档顺序从 2000 起编号（2000、2001…）；`system` 段对 SSH/SNMP 的 ACL 引用使用同一策略（代码中有一份等价实现）。若后续样本的基本 ACL 数量/顺序变化，编号会随文档顺序变化，属确定性策略而非固定答案。
- **`ACL_IPV4` 等非基本 ACL**：未实现，整组不输出并记 `unsupported`；`acl/interfaces` 绑定亦未映射。
- **BGP `additional-paths select-best 16`**：OC 只给出 `send-max`，16 为固定策略值；`send-max`/`advertise-delay` 等未映射项已报告。
- **WRED 仅映射 green 档**：`green-minth/green-maxth/green-probability` 作为 low/high/probability；red/yellow 档不输出（报告中记为 `ambiguous`）。
- **排序**：接口、实例等一律按名称的字符串序；ACL 规则按序号；BGP network 按前缀排序；dscp/dot1p 表按导入值字符串序。顺序策略属实现身份的一部分。

## 4. 有意不输出/近似映射的字段（报告中显式记录）

- `interfaces/interface/*/config/mtu`（256 处）、`ethernet/config/{auto-negotiate,duplex-mode,enable-flow-control,src-eq-dst-l3-action}`、`fec/config/enable`、`hold-time/config/down`：参考不含对应命令。
- 路由口（`interface-mode=route` 的物理口）**一律输出 `shutdown`**：样本参考对被分配但未启用的 400GE 口均输出 shutdown，即使 OC `enabled=true`；该策略已报告为 `unsupported`（`config/enabled` 未被使用）。`description` 亦不输出。
- 聚合口 `routed-vlan/config/virtual-mac-address` 不输出（仅 `IF_ROUTED_VLAN` 输出 `mac-address`）。
- ACL 规则仅映射动作与源地址；`destination-address` 非 `any` 时报 `unsupported` 并跳过该规则；`protocol`/`transport` 读入但不影响输出（`ignored`）。
- 缓冲区只映射实际出现在参考中的量：`limit-threshold`、`alarm-threshold`、百分比、headroom 池；`min-threshold`、`limit-mode`、`xon-offset-threshold`、`buffer-monitor/suppress-num` 等不输出（`unmapped`）。
- 未映射的子系统：`system/{counter,dns,nd,mirrors,hash/inner+dhash+dlb,mod/*bind-mirror-id}`、`qos/{ebst-policies,global/ebst,queues/*/wred,global/pfc/*}`、`interfaces/interface/Netsense`（tunnel 接口）、`acl` 中的高级 ACL、`telemetry-system` 中未被参考表达的高级字段、`system/sampling` 的 datagram-size/cpu-rate-limit 等。这些在报告中按路径模板聚合列出。
- `routing-policy` 中未被任何 route-policy 引用的 defined-set（如 `LOOPBACK0`）不输出（`ignored`），因为参考不输出；**注意**：这与"尽量覆盖整份输入"存在张力，选择与参考行为一致并显式报告。

## 5. 编号引用类字段缺失时的行为

- 若被引用的对象缺失（例如 `system/sampling/sflow/config/source-interface` 指向的接口不存在），翻译器记录 `error` 并跳过相关命令，不中断整体翻译。
- 输入不可用（空文件、非 UTF-8、非法 JSON、顶层非对象）时退出码 2，不产生输出文件。

## 6. 材料与设备不确定性

- 厂家 H3C 由用户确认；**样本设备真实型号、Comware/NOS 版本、配对快照是否同一时点/无损均未确认**。
- 开发参考为《H3C S9827 & S9857 系列交换机 命令参考-R932x-6W101》（导读对应 Release 9323），是按样本特征选择的**开发参考**，不是已核实的原设备手册；`references/h3c-s9827-s9857-r932x-6w101/README.md` 说明了适用边界。
- 命令语法以该官方手册为主；参考 CLI 文本只用于开发期对拍，运行时完全不读取。

## 7. 未在真实设备/模拟器上执行验证

- 生成文本按参考脚本风格输出（`return`/`system-view` 分段、连续进入接口视图、`Y` 应答行等）。它未在真实 H3C 设备或模拟器上整篇执行验证；空白与视图衔接均按参考文本复现。
- 因此"可执行性"只到参考文本一致性级别；若要用作真实开局脚本，建议先在离线模拟器验证视图切换与交互应答。

## 8. 输入模型范围

- 仅接受单个 JSON 对象文档（该实验的 OC 导出约定）；不支持 JSON Lines、多文件拆分或形式化 OC Schema 校验。
- OC 字段以开发样本出现的结构与取值为准；对结构不同但语义相同的变体（如 `trunk-vlans` 为数组/标量、多 VRF、多 ACL）做了参数化处理与冒烟验证，但未覆盖所有可能的厂商扩展字段；未知字段会进入 `unmapped` 报告而不是被静默忽略。
