# IPTV 解析器配置文件 (config.json) 使用指南 (测速优选版)

本文件旨在为您详细介绍 `config.json` 中各个参数的含义、推荐配置，并提供常见使用场景下的配置模板，帮助您轻松管理和使用 IPTV 域名解析与 IP 优选微服务。

---

## 配置文件完整参数速览

以下是包含所有可用配置项的完整结构示例：

```json
{
  "dns_servers": [],
  "use_doh": true,
  "mode": "prefer-ipv6",
  "update_interval_hours": 12,
  "keep_unresolved": false,
  "ip_speed_test": true,
  "workers": 50,
  "sources": [
    {
      "name": "zilong7728_best_sorted",
      "url": "https://github.com/zilong7728/Collect-IPTV/blob/main/best_sorted.m3u",
      "output": "best_sorted_resolved.m3u"
    }
  ]
}
```

---

## 核心配置参数详解

### 1. 域名解析与 IP 优选 (DNS & Speed Test Settings)

| 参数名 | 默认值 | 推荐配置 | 参数释义与使用建议 |
| :--- | :--- | :--- | :--- |
| **`use_doh`** | `true` | `true` (推荐) | **DNS-over-HTTPS (DoH) 引擎开关**。<br>开启后将通过安全的加密 HTTP 连接向阿里云 DoH 发起解析。**极其推荐在开启了 Clash 等本地代理的环境下使用**，能 100% 避开代理的 Fake-IP (198.18.x.x) 劫持污染，获取到绝对真实的公网 IP。 |
| **`ip_speed_test`**| `true` | `true` (推荐) | **IP 优选与连接测速开关**。<br>当域名解析出多个公网 IP（常见于各类 CDN 加速源）时，**系统会并行对这些 IP 在您的本地网络环境下进行 TCP 连接握手测速**，并自动挑选响应最快、最稳定的那个 IP 替换入 URL。<br>- **死链过滤**：如果开启了测速，且 `keep_unresolved` 为 `false`，测速不通的无效 IP 会被直接过滤。这天然起到了**剔除死链频道**的作用！<br>- **极致容错保底**：若您的网络波动导致所有 IP 均握手超时，系统会自动回退选取第一个解析 IP，确保频道不被误杀，具有 100% 可用性。 |
| **`dns_servers`** | `[]` | `[]` 或自定义 | **传统本地/公网 DNS 服务器列表**（传统 UDP 解析）。<br>- 若您需要解析局域网内的专网域名（如 AdGuard Home, 软路由 local 域名），可在此配置您的内网 DNS（如 `["192.168.1.1"]`）。<br>- **注意**：一旦在此处填入任何 IP，系统会**自动停用 DoH**，转为向您填写的 DNS 服务器发起解析。 |
| **`mode`** | `"prefer-ipv6"` | `"prefer-ipv6"` | **智能解析模式**，可选值如下：<br>- `"prefer-ipv6"`（默认）：**优先解析 IPv6**。如果域名能解析到 IPv6 地址，则优先对 IPv6 候选集进行测速优选；若所有 IPv6 均不通或解析不到，则自动降级对该域名的 IPv4 候选集进行测速并替换。<br>- `"ipv6-only"`：仅解析、测速并保留 IPv6 链接，无 IPv6 则过滤该频道。<br>- `"ipv4-only"`：仅解析、测速并保留 IPv4 链接。 |

### 2. 系统执行参数 (System Settings)

| 参数名 | 默认值 | 推荐配置 | 参数释义与使用建议 |
| :--- | :--- | :--- | :--- |
| **`update_interval_hours`**| `0` | `12` 或 `24` | **定时自动更新周期**（小时数）。<br>- 如果设置为 `0`：服务在运行完一次完整的下载、解析、测速和写出流程后，程序会**直接退出**（适合单次手动运行或配合外部 Crontab 定时调度）。<br>- 如果设置为大于 `0` 的正数（如 `12`）：程序启动后将**常驻后台运行**（作为 Docker 守护进程），每隔指定小时自动从网络下载并更新一次列表，极力推荐常驻部署时使用。 |
| **`keep_unresolved`** | `false` | `false` | **解析/测速失败频道的处理策略**。<br>- `false`（推荐）：自动将所有“解析失败或所有IP测速均不通”的失效频道在输出文件中**过滤丢弃**，确保您最终生成的播放列表 100% 极速可用。<br>- `true`：对于失效的域名，在输出文件中保留原域名链接不变。 |
| **`workers`** | `50` | `50` | **并发解析与测速线程数**。多线程并行发起 DNS 解析与 TCP 握手测速，大幅缩短等待时间。通常对于 200 个唯一连接的列表，设置为 `50` 可以在 10~15 秒内轻松搞定全部解析与测速优选。 |

### 3. 数据源参数 (Sources Settings)

**`sources`** 是一个 JSON 数组，您可以在其中配置任意多个不同的 IPTV 节目列表网络链接。每个源包含 3 个配置项：

- **`name`**：自定义的数据源别名，仅用于日志打印中便于区分。
- **`url`**：网络订阅链接地址。
  - **支持格式**：`.m3u` / `.m3u8` / `.txt` 等类型的文件。
  - **GitHub 自动转换**：工具已为您内置了 GitHub URL 翻译器。如果您填入的是 GitHub 网页端的浏览链接（如含有 `/blob/`），系统在下载前会**自动将其智能转换为 raw 纯文本链接**（如 `raw.githubusercontent.com`），无需您手动操作！
- **`output`**：解析替换完成后，输出到本地 `/app/output/` 目录下的目标文件名（如 `iptv_v6.m3u` 或 `channels.txt`）。**系统会根据输入源的内容，自动判断并完美保留其原有的 M3U 或 TXT 格式**。

---

## 典型应用场景配置模板

### 场景 A：绕过代理污染 + 测速优选 + 优先 IPv6（最推荐的公网更新模板）
> 适用于在本地开启了代理的宿主机，或部署在具有公网双栈环境的服务器（如 NAS、VPS），想要生成经过网速优选的高品质真实播放列表。

```json
{
  "dns_servers": [],
  "use_doh": true,
  "mode": "prefer-ipv6",
  "update_interval_hours": 12,
  "keep_unresolved": false,
  "ip_speed_test": true,
  "workers": 50,
  "sources": [
    {
      "name": "cctv_main",
      "url": "https://github.com/zilong7728/Collect-IPTV/blob/main/best_sorted.m3u",
      "output": "cctv_resolved.m3u"
    }
  ]
}
```

### 场景 B：软路由/局域网专网域名解析（适合有特殊内网 DNS 需求的用户）
> 适用于需要解析局域网特定专网域名（如 AdGuard Home, 软路由 hosts），不担心公网代理 Fake-IP 污染的环境。

```json
{
  "dns_servers": ["192.168.1.1", "119.29.29.29"],
  "use_doh": false,
  "mode": "prefer-ipv6",
  "update_interval_hours": 24,
  "keep_unresolved": false,
  "ip_speed_test": true,
  "workers": 30,
  "sources": [
    {
      "name": "local_source",
      "url": "http://router.local/list.m3u",
      "output": "local_resolved.m3u"
    }
  ]
}
```
