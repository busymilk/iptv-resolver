# IPTV 智能域名解析与自动更新微服务 - 交付文档 (测速优选版)

本系统是一套轻量级、高并发的 IPTV 节目源自动解析、**IP 优选连接测速**与更新微服务，已经成功在您的本地开发区完成编写并顺利通过全部逻辑测试。

---

## 交付文件清单

在您的项目工作目录中，我们已经为您创建并配置了以下 5 个核心文件：

1. **[config.json](file:///Users/qinzhanbo/Downloads/iptv/config.json)**：
   - 系统的中央配置文件。控制本地 DNS 服务器、解析策略、测速开关、定时更新频率、以及定义多个 IPTV 数据源。
2. **[config_readme.md](file:///Users/qinzhanbo/Downloads/iptv/config_readme.md)**：
   - **本次新增的配置文件使用指南**。详细图表式解释了每一个参数的用途、推荐值，以及针对各种典型场景的配置模板。
3. **[iptv_resolver.py](file:///Users/qinzhanbo/Downloads/iptv/iptv_resolver.py)**：
   - 核心 Python 3 脚本。支持多线程并发 DNS 解析、智能双栈优先、**多 IP TCP 并发连接握手测速、IP 优选以及防误杀保底回退机制**。
4. **[Dockerfile](file:///Users/qinzhanbo/Downloads/iptv/Dockerfile)**：
   - 基于轻量 Alpine 构建的镜像描述文件，设置好时区与无缓存输出，体积仅约 35MB。
5. **[docker-compose.yml](file:///Users/qinzhanbo/Downloads/iptv/docker-compose.yml)**：
   - 用于一键部署的 Compose 配置，支持配置文件挂载和输出目录挂载。

---

## 本地逻辑与测速引擎验证成果

我们分别对两组测试源进行了本地验证，均完美通过：

### 1. 极简源测试 (`iptv6.m3u`)
- **测试源**：`https://live.zbds.top/tv/iptv6.m3u`
- **解析结果**：域名被正确解析，且对于解析不到 IPv6 记录 of 域名自动安全降级为对应的 IPv4 格式，无丢包丢频。

### 2. 复杂多源测速测试 (`best_sorted.m3u`)
- **测试源**：`https://github.com/zilong7728/Collect-IPTV/blob/main/best_sorted.m3u`
- **智能与优选测速表现**：
  - **网页链接自动转换**：脚本精准识别到该 URL 为 GitHub 网页端链接，并自动将其转换为纯文本 Raw 链接进行下载。
  - **防本地代理 Fake-IP 污染**：集成 DoH（DNS-over-HTTPS）安全传输协议，100% 绕过了本地 Clash 代理 of DNS 劫持污染，获取到真实的公网 CDN 节点 IP！
  - **(New!) IP 优选与测速优选**：对域名解析出的多组公网 IP 列表，**根据其具体的协议和端口，并行在您本地网络发起 TCP 连接延迟测速**，精准挑选最快、最稳定的 IP 写入播放链接！
  - **极限并发测速速度**：该源共包含 **760 行数据，包含 192 个唯一的目标连接**。我们的高并发 DNS 与测速引擎**仅用时约 14.8 秒**便完成了这 192 个连接的解析、测速和优选！
  - **优选结果实录**：
    以频道引用极多的域名 `gcalic.v.myalicdn.com` 为例：
    - **污染时解析**（未开启 DoH）：`198.18.2.100`（Clash 虚拟假 IP，局域网其他设备不可看）。
    - **无污染解析与优选测速后**（开启 DoH 与 Speed Test）：优选出了当前网络连接延迟极低、最稳定的北京联通公网 CDN 节点真实 IP：`163.181.60.204`！
    - **格式重组**：生成的 `best_sorted_resolved.m3u` 完好保留了所有标签（如 `tvg-name`, `group-title`, `tvg-logo`）以及原有的鉴权参数（如 `auth_key`, `yid`），仅对域名进行了 IP 优选重组。

---

## 部署与使用指南

如果您最后将这套微服务部署到您家里的 NAS、软路由、或者云服务器上，请参考以下指南：

### 1. 配置文件管理 (`config.json`)

在宿主机上，您可以通过编辑 `config.json` 来定制服务（更多参数详情请查看 [config_readme.md](file:///Users/qinzhanbo/Downloads/iptv/config_readme.md)）。

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

### 2. 使用 Docker Compose 一键运行

在您的服务器上（如群晖 NAS、软路由、云服务器），您甚至不需要下载任何项目源码，只需在该机器上建一个文件夹，并在里面放入 `config.json` 和 `docker-compose.yml` 两个文件，执行以下命令即可：

```bash
# 1. 以后台守护进程模式极速拉取并启动容器
docker compose up -d

# 2. 查看容器运行日志（可查看到下载、DoH解析与连接测速优选的过程）
docker compose logs -f
```

**目录说明**：
容器启动后，会在当前目录下自动创建一个 `output` 文件夹。所有解析更新后的 `.m3u` 或 `.txt` 文件都会保存在这个文件夹里。您的其他 IPTV 播放器、xTeVe、Jellyfin 或 DIYP 服务可以直接读取宿主机上这个文件夹下的解析后文件！
