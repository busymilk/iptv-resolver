# IPTV 解析器配置文件 (config.json) 使用指南

本指南旨在详细介绍 `config.json` 中各个参数的定义、取值范围、推荐配置，并提供典型场景下的配置模板，帮助您灵活使用 IPTV 域名解析、IP 测速排序、流媒体播放可用性测试与可视化配置管理后台。

---

## 配置文件完整参数示例

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
  "max_channels_per_title": 3,
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

## 🚀 核心机制说明

### 1. 同名电视频道自动测速与排序
* **机制**：当您的抓取源中同一个电视频道存在多个不同播放源链接（如连续出现多个同名的 `CCTV-1`，或者一个域名解析出了多个 CDN IP 并生成了多个播放 URL）时，系统会自动将它们进行同名聚合。
* **效果**：系统在对这些视频源链接完成拉流测试后，会根据其实测响应时间（秒）进行升序排序，使最快、最稳定的链接排在前面，保障播放器秒开首选，并按延迟顺次备用切换。

### 2. 慢源冗余剔除机制
* **机制**：由参数 `max_channels_per_title` 控制。
* **效果**：如果同一个电视台可用的播放源线路或多 IP 路线非常多，在经过排序后，系统只截取前 N 个响应最快的源，将剩下较慢的冗余源自动剔除抛弃，从而保持播放列表的精简。

### 3. 可视化 Web 管理后台
* **功能**：工具内置了 Web 服务器，支持在浏览器中可视化修改全局配置、动态增删改网络订阅源、一键保存并自动热重载。
* **监控**：后台界面最下方嵌入了运行日志终端视窗，会定时自动静默轮询更新，以便掌控测速与排序过滤细节。

---

## 核心配置参数详解

### 1. 局域网服务配置 (Web Settings)

| 参数名 | 默认值 | 推荐配置 | 参数释义与使用建议 |
| :--- | :--- | :--- | :--- |
| **`web_port`** | `8080` | `8080` (可选) | **局域网共享与可视化后台端口**。<br>- **可选配置**：若不写此项，系统默认开启 8080 端口提供文件订阅与后台页面。<br>- 若设为 `0`：则彻底关闭 Web 服务，脚本在单次处理完数据后直接退出。<br>- 若设为大于 `0` 端口数：<br>1. **配置后台**：浏览器打开 `http://<服务器IP>:{port}/` 即可访问后台管理界面。<br>2. **电视订阅**：电视端填入 `http://<服务器IP>:{port}/output/<文件名>` 极速拉取播放。 |

### 2. 局部数据源专属策略 (Per-Source Settings)

在 **`sources`** 数据源列表数组中，您可以为每个网络源配置局部专属的解析策略：
* **局部字段：`mode`**（可选值：`"prefer-ipv6"`、`"ipv6-only"`、`"ipv4-only"`）。
* **作用**：当配置为 `"ipv6-only"`（或 `"ipv4-only"`）时，系统会对该源进行绝对的协议限制。一旦其域名未解析出所要求的 IP 类型，**该条目会被直接当作解析失败过滤掉，而不会走“降级备用”逻辑**。这适用于需要对特定源进行纯协议过滤的高级场景。

### 3. 全局解析与测试配置 (Global DNS & Test Settings)

| 参数名 | 默认值 | 推荐配置 | 参数释义与使用建议 |
| :--- | :--- | :--- | :--- |
| **`dns_servers`** | `[]` (留空) | `[]` (防劫持保底) | **智能 DNS / DoH 服务器列表**。<br>- **可选配置**：若留空，系统默认并行使用阿里云与腾讯云的公网 DoH 解析，以避开本地 DNS 劫持污染。<br>- **混配支持**：支持普通 DNS IP（如 `223.5.5.5`）与 https:// 开头的 DoH 链接（如 `https://dns.alidns.com/resolve`）灵活混配。 |
| **`web_proxy`** | `false` | `true` (推荐) | **流媒体代理中转与 Host/SNI 自动透传开关**（新特性）。<br>- 开启后，播放列表的链接会被自动改写为由本地服务器中转代理的格式。<br>- **电视零配置**：无需在电视上修改 hosts，后台强行使用 socket 劫持 IP 进行 TCP 通信，同时在 TLS/HTTP 层面完美保留域名的 Host 与 SNI 头，完美绕过 HTTPS 防盗链 403 / 证书不匹配报错。<br>- **动态自适应**：电视端获取订阅文件时，播放前缀会自动、动态地替换为电视当前请求时的真实局域网 IP，无需用户手动配置 IP。 |
| **`ip_speed_test`**| `true` | `true` | **IP 优选与连接测速开关**。<br>当不开启流媒体实际播放测试时，系统会在本地发起多线程 TCP 连接测速，挑选出延迟最低的那个 IP 替换入播放 URL。 |
| **`media_stream_test`**| `true` | `true` | **流媒体实际播放拉流测试开关**（推荐）。<br>开启后，会对域名解析出的所有 IP 候选分别生成播放 URL 并进行实际的 HTTP 拉流测试，读取首包数据验证可用性。100% 拦截并剔除 403 Forbidden、404 Not Found 或拉流卡死等假源。 |
| **`media_stream_timeout`**| `3.0` | `3.0` | **流媒体拉流测试超时时间（秒）**。<br>如果在该时间内无法成功建立连接并读取到首包数据，则判定为无法播放并过滤抛弃（当 `keep_unresolved` 为 `false` 时）。 |
| **`max_channels_per_title`**| `3` | `3` (推荐 3-5) | **同一个电视台保留的最快可用源数量上限**。<br>在所有可用播放源（包含多 IP 和多路线）排序完成后，每个电视台只保留速度最快的前 N 个链接，将多余的慢源自动剔除，保持列表精练。 |
| **`keep_unresolved`** | `false` | `false` | **解析/测速/测试失败保留策略**。<br>设为 `false`（推荐）时，解析失败、测速超速或无法正常拉流播放的无效频道会被自动过滤抛弃，确保播放列表内链接均能正常播放。 |

---

## 典型配置场景推荐

### 🎯 场景配置：混合源精细化过滤 + 局域网电视一键订阅 (终极推荐)

> 适用于家里有多路网络，其中有 M3U 源只在 IPv6 下稳定，而有 TXT 源只需 IPv4 解析，且想直接在电视上输入局域网地址进行自动更新的场景。

```json
{
  "dns_servers": [],
  "update_interval_hours": 12,
  "keep_unresolved": false,
  "ip_speed_test": true,
  "media_stream_test": true,
  "media_stream_timeout": 3.0,
  "max_channels_per_title": 3,
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

假如运行该 Docker 容器的服务器（如群晖 NAS、软路由）的局域网 IP 是 `192.168.31.5`：
1. **电视配置源一 (双栈优选源)**：
   `http://192.168.31.5:8080/output/cctv_v6_v4.m3u`
2. **电视配置源二 (纯 IPv6 强制过滤源)**：
   `http://192.168.31.5:8080/output/cctv_only_v6.m3u`
3. **电视配置源三 (纯 IPv4 强制过滤源)**：
   `http://192.168.31.5:8080/output/cctv_only_v4.m3u`

容器常驻后台，电视每次启动都会自动从本地服务器拉取经过并发播放拉流测试、测速重新排序和限流剔除慢源后的纯净播放列表，告别卡顿与黑屏！
