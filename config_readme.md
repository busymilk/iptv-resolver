# IPTV 解析器配置文件 (config.json) 使用指南 (Web后台+多源重排版)

本文件旨在为您详细介绍 `config.json` 中各个参数的含义、推荐配置，并提供常见使用场景下的配置模板，帮助您轻松管理和使用 IPTV 域名解析、多 IP 优选、**同名多源网速重排序**与 **内置 Web 可视化管理后台**。

---

## 配置文件完整参数速览

以下是包含所有可用配置项的完整结构示例：

```json
{
  "dns_servers": [],
  "use_doh": true,
  "update_interval_hours": 12,
  "keep_unresolved": false,
  "ip_speed_test": true,
  "media_stream_test": true,
  "media_stream_timeout": 3.0,
  "workers": 50,
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
    },
    {
      "name": "ipv4_only_test",
      "url": "https://live.zbds.top/tv/iptv6.m3u",
      "output": "ipv4_only_test.m3u",
      "mode": "ipv4-only"
    }
  ]
}
```

---

## 🚀 重磅核心新特性介绍

### 1. 同名电视频道“多视频源自动测速重排序 (Speed Auto-Sorting)”
本服务集成了业界领先的 **“双层 IP 优选与多源重排算法”**：
- **第一层 (域名级)**：对单个链接的域名解析出的多个 IP，连接 TCP 测速并提取最快 IP 替换域名。
- **第二层 (源级别)**：当您的订阅源中**同一个电视台存在多个不同的视频源链接**（如连续出现多个同名的 `CCTV-1`）时，系统会自动进行**同名聚合**，在所有链接完成首轮 IP 解析和测速后，**根据它们的延迟耗时（秒）进行升序重排序（速度最快最稳定的链接排在最前面）**。这保证了播放器在加载时秒开首选，并能按网速顺次备用切换！

### 2. 内置可视化 Web 管理配置后台 (Visual Config Web GUI)
服务内置了多线程 Web 服务器与 API 控制后端。无需额外配置 Nginx、Caddy，也无需手动登录 SSH 修改配置文件！
- **访问地址**：局域网任意浏览器直接访问 `http://<您的服务器IP>:<web_port>/` (如 `http://192.168.1.100:8080/`)。
- **极致功能**：
  - 玻璃拟态亮白高透精致设计（Light Mode）。
  - **开机即时秒开响应**：内置 Web 服务器已与解析测速引擎完全解耦，启动瞬间即可立即响应，绝不阻塞 Web 及旧文件的拉取。
  - **上次与预计下次更新时间**：界面实时展示历史更新时间与预估定时更新时间提示，自动计算。
  - **表单化全局配置**：滑块式管理测速开关、高并发执行线程数，并在 DNS 处支持传统 IP 与 DOH 链接的灵活混合配置。
  - **嵌入式系统运行日志 (New!)**：管理面板最下方直连滚动日志文件，3 秒自动静默轮询更新并自动滚屏，极致优雅。
  - **一键保存并自动热重载**：保存配置后微服务自动在内存中生效。
  - **流光一键触发解析更新**：点击【立即触发解析测速更新】大按钮，云端/服务器自动异步进行高并发解析与重排，前端 Loading 遮罩展示进度，完成后 Toast 提示。

---

## 核心配置参数详解

### 1. 局域网后台与文件共享服务 (Web Settings)

| 参数名 | 默认值 | 推荐配置 | 参数释义与使用建议 |
| :--- | :--- | :--- | :--- |
| **`web_port`** | `8080` | `8080` (可选) | **局域网共享与配置后台端口**。<br>- **可选配置**：若不配置此项，系统**缺省默认开启 8080 端口**提供 Web 共享及可视化后台服务。<br>- 若设为 `0`：则彻底关闭 Web 服务。<br>- 若设为大于 `0` 的端口数：<br>1. **配置后台**：浏览器打开 `http://<服务器IP>:{port}/` 即可访问后台管理界面。<br>2. **电视订阅**：电视端填入 `http://<服务器IP>:{port}/output/<文件名>` (如 `http://192.168.1.100:8080/best_sorted_resolved.m3u`) 极速拉取播放。 |

### 2. 精细化数据源局部策略 (Per-Source Resolution Settings)

在 **`sources`** 数据源列表数组中，您可以为每个源配置专属的解析策略：
- **局部字段：`mode`**（可选值：`"prefer-ipv6"`、`"ipv6-only"`、`"ipv4-only"`）。
- **忽略与强制忽略策略**：当您将某个数据源局部配置为 `"ipv6-only"`（或 `"ipv4-only"`）时，**系统会对该源进行绝对的协议限制**。一旦域名无法解析出您要求的 IP 类型（比如选了 ipv6-only，但域名只有 ipv4 地址），**该链接会被直接当作解析失败过滤掉，而不会走“降级备用”逻辑**。这完美适应了您针对不同源进行纯物理协议隔离过滤的高阶需求！

### 3. 全局解析与测速 (Global DNS & Speed Test Settings)

| 参数名 | 默认值 | 推荐配置 | 参数释义与使用建议 |
| :--- | :--- | :--- | :--- |
| **`dns_servers`** | `[]` (留空) | `[]` (防劫持保底) | **智能 DNS / DoH 服务器列表**。<br>- **可选配置**：若不写此参数或留空，系统**缺省默认并行启用阿里云与腾讯云的公网 DoH 解析**，100% 避开 Fake-IP 代理污染。<br>- **高度灵活**：支持普通 DNS IP（如 `223.5.5.5`）与 **https:// 开头的加密 DoH 服务器**（如 `https://dns.alidns.com/resolve`）混配！ |
| **`ip_speed_test`**| `true` | `true` | **IP 优选与连接测速开关**。<br>多 IP 候选集会在您的本地网络发起多线程 TCP 连接延迟测速，自动挑选延迟最低、最稳定的那个 IP 替换入播放 URL。 |
| **`media_stream_test`**| `true` | `true` | **流媒体实际播放拉流测试**。<br>- **可选配置**：开启后（推荐），会对同一个域名解析出的所有候选 IP 分别生成播放 URL 并进行实际拉流测试。<br>- 100% 过滤掉返回 403、404、5xx 或者连接成功但无法拉取流数据的无效源。<br>- 对于可正常播放的多个 IP 备选源，将以实际的秒开响应时间（Time to First Byte, TTFB）作为测速延迟，在同名电视台合并中升序重排序，最快的排在最前面，并保留其它可播 IP 作为多源备份！ |
| **`media_stream_timeout`**| `3.0` | `3.0` | **流媒体拉流测试超时时间（秒）**。<br>如果在此超时时间内无法建立连接并拉取到首包数据，则判定为该链接无法正常播放并进行过滤（当 `keep_unresolved` 为 `false` 时）。 |
| **`keep_unresolved`** | `false` | `false` | **解析/测速/播放测试失败策略**。<br>设为 `false`（推荐）时，解析失败、测速超速或无法正常拉流播放的无效频道会被自动过滤抛弃，确保播放列表 100% 正常播放且秒开秒连。 |

---

## 典型配置场景推荐

### 🎯 场景配置：混合源精细化过滤 + 局域网电视一键订阅 (终极推荐)
> 适用于家里有多路网络，其中有 M3U 源只在 IPv6 下稳定，而有 TXT 源只需 IPv4 解析，且想直接在电视上输入局域网地址进行秒级更新的场景。

```json
{
  "dns_servers": [],
  "update_interval_hours": 12,
  "keep_unresolved": false,
  "ip_speed_test": true,
  "workers": 50,
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
    },
    {
      "name": "strict_ipv4_only",
      "url": "https://live.zbds.top/tv/iptv6.m3u",
      "output": "cctv_only_v4.m3u",
      "mode": "ipv4-only"
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
3. **电视配置源三 (纯 IPv4 强制过滤源)**：
   `http://192.168.31.5:8080/cctv_only_v4.m3u`
4. 容器常驻后台，电视每次启动都会自动从您的这台本地服务器拉取经过最新高并发优选测速后的纯净公网链接，彻底告别卡顿！
