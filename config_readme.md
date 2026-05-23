# IPTV 解析器配置文件 (config.json) 使用指南 (局域网共享+单源模式版)

本文件旨在为您详细介绍 `config.json` 中各个参数的含义、推荐配置，并提供常见使用场景下的配置模板，帮助您轻松管理和使用 IPTV 域名解析、IP 优选与局域网共享微服务。

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
  "web_port": 8080,
  "sources": [
    {
      "name": "zilong7728_best_sorted",
      "url": "https://github.com/zilong7728/Collect-IPTV/blob/main/best_sorted.m3u",
      "output": "best_sorted_resolved.m3u"
    },
    {
      "name": "ipv6_only_test",
      "url": "https://live.zbds.top/tv/iptv6.m3u",
      "output": "ipv6_only_test.m3u",
      "mode": "ipv6-only"
    }
  ]
}
```

---

## 核心配置参数详解

### 1. 局域网 Web 共享服务器 (LAN Web Sharing)

| 参数名 | 默认值 | 推荐配置 | 参数释义与使用建议 |
| :--- | :--- | :--- | :--- |
| **`web_port`** | `0` | `8080` (推荐) | **局域网共享 HTTP 端口**。<br>- 若设为 `0`：不开启共享服务。<br>- 若设为大于 `0` 的端口数（如 `8080`）：微服务会在后台自动拉起一个轻量级多线程 Web 文件服务器，**把整个 `output/` 文件夹广播到您的家庭局域网中**！<br>- **电视访问极简地址**：您的电视盒子、小薇直播、Kodi 或 DIYP 播放器，可以直接填写 `http://<您运行本服务的机器IP>:8080/<输出文件名>` (例如: `http://192.168.1.100:8080/best_sorted_resolved.m3u`) 自动拉取更新后的列表进行播放！ |

### 2. 精细化数据源解析策略 (Per-Source Resolution Settings)

在 **`sources`** 数据源列表数组中，您不仅可以为每个源配置 `name`, `url` 和 `output`，还能为特定数据源设置 **专属的解析策略**：

* **局部模式字段：`mode`**
  - **默认值**：如果不配置，该数据源会继承全局的 `mode`（默认优先 IPv6，降级 IPv4）。
  - **可选覆盖值**：`"prefer-ipv6"`、`"ipv6-only"`、`"ipv4-only"`。
  - **忽略与强制忽略策略**：当您将某个数据源局部配置为 `"ipv6-only"`（或 `"ipv4-only"`）时，**系统会对该源进行绝对的协议限制**。一旦域名无法解析出您要求的 IP 类型（比如选了 ipv6-only，但域名只有 ipv4 地址），**该链接会被直接当作解析失败过滤掉，而不会走“降级备用”逻辑**。这完美适应了您针对不同源进行纯 IPv6 / 纯 IPv4 划分过滤的高阶需求！

### 3. 全局解析与测速 (Global DNS & Speed Test Settings)

| 参数名 | 默认值 | 推荐配置 | 参数释义与使用建议 |
| :--- | :--- | :--- | :--- |
| **`use_doh`** | `true` | `true` | **DNS-over-HTTPS (DoH) 引擎开关**。<br>通过安全的加密连接向阿里云 DoH 发起解析。**极其推荐在开启了 Clash 的环境使用**，能 100% 避开代理的 Fake-IP (198.18.x.x) 劫持污染，获取到绝对真实的公网 IP。 |
| **`ip_speed_test`**| `true` | `true` | **IP 优选与连接测速开关**。<br>多 IP 候选集会在您的本地网络发起多线程 TCP 连接延迟测速，自动挑选延迟最低、最稳定的那个 IP 替换入播放 URL。 |
| **`keep_unresolved`** | `false` | `false` | **解析/测速失败策略**。<br>设为 `false`（推荐）时，解析失败或测速全部超时的无效频道会被自动过滤，确保播放列表 100% 极速可用。 |

---

## 典型配置场景推荐

### 🎯 场景配置：混合源精细化过滤 + 局域网电视一键订阅 (终极推荐)
> 适用于家里有多路网络，其中有 M3U 源只在 IPv6 下稳定，而有 TXT 源只需 IPv4 解析，且想直接在电视上输入局域网地址进行秒级更新的场景。

```json
{
  "dns_servers": [],
  "use_doh": true,
  "mode": "prefer-ipv6",
  "update_interval_hours": 12,
  "keep_unresolved": false,
  "ip_speed_test": true,
  "workers": 50,
  "web_port": 8080,
  "sources": [
    {
      "name": "cctv_dual_stack",
      "url": "https://github.com/zilong7728/Collect-IPTV/blob/main/best_sorted.m3u",
      "output": "cctv_v6_v4.m3u"
    },
    {
      "name": "strict_ipv6_only",
      "url": "https://live.zbds.top/tv/iptv6.m3u",
      "output": "cctv_only_v6.m3u",
      "mode": "ipv6-only"
    }
  ]
}
```

#### 📺 在电视端（如 DIYP, Kodi）的配置方法：
假如您运行该 Docker 容器的服务器（如群晖 NAS、软路由）的局域网 IP 是 `192.168.31.5`：
1. **电视配置源一 (双栈优选源)**：
   `http://192.168.31.5:8080/cctv_v6_v4.m3u`
2. **电视配置源二 (纯 IPv6 强制过滤源)**：
   `http://192.168.31.5:8080/cctv_only_v6.m3u`
3. 容器常驻后台，电视每次启动都会自动从您的这台本地服务器拉取经过最新高并发优选测速后的纯净公网链接，彻底告别卡顿！
