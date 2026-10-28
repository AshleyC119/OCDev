# 支持范围（Support）

翻译器对"完整 OC 文档"做整篇翻译：按固定顺序把 OC 子树映射为 H3C CLI 配置块。下表给出当前实现覆盖的输入域与产出命令。所有取值来自 OC；固定命令关键字/模板若 OC 无法表达，会在报告中记为 `ambiguous`；OC 中存在但当前未映射的内容记为 `unsupported` / `ignored` / `unmapped`。

## 全局对象

| OC 来源 | CLI 产出 | 说明 |
| --- | --- | --- |
| `network-instances/network-instance`（`type`=`L3VRF`） | `ip vpn-instance <name>`、`route-distinguisher <rd>` | 每个 VRF 一个块 |
| 同一 VRF 的 `interfaces/interface` | `interface <if>` + `ip binding vpn-instance <vrf>` | 管理 VRF 绑定 |
| `.../protocols/protocol`（`identifier`=`STATIC`） | `ip route-static [vpn-instance <vrf>] <net> <len> [if] [nh]  preference <m> description <d>` | 支持多下一跳；`preference` 前的双空格为参考文本格式 |
| `network-instances/.../global/vlans/vlan` | `vlan <id>`、`description <name>` | 末尾保留 `system-view`/`#` 分隔行 |
| `acl/acl-sets/acl-set`（`type`=`ACL_CTRL`） | `acl number <n> `、`acl basic <n>`、`description`、`rule <seq> <permit/deny>  vpn-instance <vrf> source <ip> <wildcard>    ` | 基本 ACL；编号为翻译器策略（见限制）；仅映射源地址与动作 |
| `routing-policy/policy-definitions`、`defined-sets` | `route-policy ... permit/deny node N`、`if-match ...`、`apply ...`、`ip community-list ...`、`ip prefix-list ...` | 与 BFD 同段输出 |
| `network-instances/.../BGP` | `bgp <as>`、`router-id`、`bgp update-delay on-startup`、`compare-different-as-med`、`group`/`peer ...`、`address-family ipv4 unicast` 下的 `import-route`、`balance`、`preference`、`additional-paths`、`network ... route-policy`、`peer ... enable/route-policy/...` 及交互应答行 `Y` | 见限制中的固定常量/推导说明 |

## 接口（324 个样本接口，按 CLI 名称排序）

| 类型 | 产出 |
| --- | --- |
| `IF_AGGREGATE` | `interface Bridge-AggregationN`、`description`、`undo shutdown`/`shutdown`、`link-aggregation mode dynamic`（LAG=LACP）、`port link-type trunk`、`undo port trunk permit vlan 1`、`port trunk permit vlan <list>`、`port trunk pvid vlan <native>` |
| `IF_ETHERNET`（`interface-mode`=`route`） | `shutdown`、`port link-mode route`、`Y`、`speed <kbps>`、`port fec mode <mode>`、`link-delay up <s>`、`flow-interval` |
| `IF_ETHERNET`（bridge） | `description`、`shutdown`/`undo shutdown`、`port link-mode bridge`、`Y`、trunk 配置、`port link-aggregation group <n>`、`speed`、`link-delay`、`flow-interval`、`{multicast,unicast,broadcast}-suppression pps` |
| `IF_ETHERNET`（无 ethernet 容器，如 M-Gig） | `description`、`undo shutdown`、`ip address ...` |
| `IF_LOOPBACK` | `undo shutdown`、`ip address ...` |
| `IF_ROUTED_VLAN`（OC 名 `Vlan<N>` → CLI `Vlan-interface<N>`） | `description`、`undo shutdown`、按 IP 排序的主/从地址（`ip address ... [sub]`）、`local-proxy-arp enable`、`arp route-direct advertise`、`mac-address <h3c>` |

## 特性段（与参考文本的分段顺序一致）

| 段 | OC 来源 | 产出 |
| --- | --- | --- |
| qos map（dscp→dot1p） | `qos/scheduler-policies` 中带 dscp 条件的策略 | `qos map-table dscp-dot1p` + `import <dscp> export <lp>` |
| PFC | `qos/interfaces/*/input/queues/queue*`（pfc/pfc-deadlock/优先级）+ `components` 的 SHARED_BUFFER/HEADROOM 门限 | `qos trust dscp`、`priority-flow-control enable`、`priority-flow-control deadlock enable`、`priority-flow-control no-drop dot1p <p> pause-threshold ratio <r> headroom <h>` |
| PFC 死锁 | `qos/global/pfc-deadlock` | `priority-flow-control deadlock ...` 系列 |
| WRED | `qos/interfaces/*/output/queues/queue4|5` → `qos/wred-policies` | `qos wred queue <q> low-limit <green-minth> high-limit <green-maxth> discard-probability <green-probability> ecn` |
| WFQ | 接口队列 `scheduler-policy` + 对应策略权重 | `qos wfq byte-count`、`qos wfq <q> group 1 byte-count <w>`、`qos wfq <q> group sp` |
| LLDP | `lldp` | `lldp global enable`、`lldp ignore-pvid-inconsistency`、每接口 `lldp tlv-enable ...` 或 `lldp admin-status <s>` |
| DHCP | `relay-agent/dhcp` | `dhcp enable` |
| LACP / S-MLAG | `lacp` | `lacp system-mac/system-number/system-priority`、每聚合口 `port s-mlag group <n>`、`lacp edge-port`、成员口 `lacp period short` |
| BFD | `bfd/interfaces` | `bfd detect-multiplier`、`bfd min-transmit-interval`、`bfd min-receive-interval` |
| INT/iFIT | `int` | `telemetry ifa global enable`、`telemetry ifa device-id`、每接口 `telemetry ifa role transit` |
| 终端线路 | `system/tty`、`system/vty` | `line aux 0` / `line vty 0 63` + `authentication-mode scheme` + `user-role ...` |
| Monitor-link | `system/monitor-link` | `monitor-link group <n>`、`downlink up-delay`、每成员口 ` port monitor-link group <n> downlink|uplink` |
| 系统服务 | `system/*`（icmp/config/clock/ssh-server/logging/ntp/snmp/arp 等） | `ip unreachables enable`、`sysname`、`header login`、`clock timezone`、`ssh ...`、`info-center ...`、`ntp-service ...`、`snmp-agent ...`、`arp timer aging ...` |
| sFlow | `system/sampling/sflow` + `system/hash` | `ip load-sharing ...`、`sflow agent/source/collector`、每接口 `sflow flow collector/sampling-rate/sampling-direction` |
| AAA | `system/aaa`、`system/config/domain-name` | `password-control` 取消项、`local-user ...`、`ssh user ...`、`hwtacacs scheme ...`、`domain ...` |
| Telemetry | `telemetry-system`、`system/grpc` | `grpc enable`、`telemetry`、`sensor-group`/`sensor path`、`destination-group`、`subscription ...` |
| 缓冲区 | `components/component/buffer` | `buffer threshold alarm ...`、每接口每队列 `buffer usage threshold headroom`、`buffer egress/ingress ...`、`priority-flow-control poolid 0 headroom` |
| MOD | `system/mod/telemetry` | `telemetry apply flow-group system-defined ip`、`telemetry mod`、`reason-list ...`、`device-id`、`reporting-interval` |

## 报告语义

- `unsupported`：OC 中存在但当前没有 CLI 映射（逐字段/逐实例聚合）。
- `ignored`：读入但不产生 CLI 效果（例如与键重复的元数据）。
- `ambiguous`：映射决策无法由文档唯一确定（编号策略、固定关键字、口径选择等），给出 `resolution`。
- `error`：输入异常（缺字段、类型不符、引用对象缺失等），翻译继续。
- `coverage`：全部数据叶子、已映射叶子、重复元数据叶子、未映射内容叶子。
- `unmapped`：未映射内容按路径模板聚合的明细（与 `coverage.missing` 对应）。

## 运行约束

- 离线、确定性：不联网、不调用模型、运行时不读取任何参考 CLI 文本。
- 每次运行对相同输入产生逐字节相同输出（`output.cli_sha256` 可复核）。
- 仅依赖 Python 标准库。
