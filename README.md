# IPTV 智能域名解析与自动更新微服务 (DoH & IP 优选测速版)

这是一套轻量级、高并发的 IPTV 节目源自动网络抓取、**DoH 加密域名解析、IP 优选连接测速**与更新的自包含微服务。

本服务旨在解决 IPTV 域名解析中的两大核心痛点：
1. **防本地代理 Fake-IP 污染**：集成 DoH (DNS-over-HTTPS) 引擎，100% 避开本地 Clash / 代理客户端对传统 DNS 的 Fake-IP 劫持，确保解析出真实的公网 IP（使导出的列表能分发到家庭电视等其他设备正常播放）。
2. **IP 优选与测速**：当一个域名解析出多个公网 CDN 地址时，脚本会在本地发起多线程高并发 TCP 握手测速，挑选出**连接响应延迟最低、最稳定**的那个 IP 替换入播放 URL。

---

## 🚀 项目特色
- **双栈智能解析**：优先尝试解析 AAAA 记录获取 IPv6 规范地址（带中括号 `[...]`），若无 IPv6 或不可达，自动降级尝试 A 记录获取 IPv4。
- **超强并发性能**：多线程高并发解析与 TCP 连接测速，**190 个连接的解析、测速与优选可在 15 秒内全部搞定**！
- **定时更新守护**：内置定时循环更新服务。只需一次部署，即可设定更新频率，作为后台守护进程实时维护。
- **智能链接识别**：内置 GitHub URL 翻译器。如果填入 GitHub 网页端订阅链接，脚本会自动翻译成 Raw 纯文本订阅链接进行抓取。
- **死链自动剔除**：在测速模式下，若某域名所有 IP 均彻底不可达（且开启了过滤策略），该频道会被自动过滤，确保生成的播放列表 100% 极速可用。
- **极致容错保底**：若遇网络波动导致所有测速均超时，系统会自动回退选取第一个解析 IP，确保频道不被误杀。

---

## 📂 项目结构
```text
├── config.json          # 核心配置文件（DNS/更新周期/数据源列表）
├── config_readme.md     # 配置文件详尽使用指南
├── iptv_resolver.py     # 核心 Python 解析与测速服务脚本
├── Dockerfile           # 轻量化 Docker 容器构建描述文件 (Alpine, ~35MB)
├── docker-compose.yml   # Docker Compose 一键启动配置文件
└── README.md            # 项目主页说明文档
```

---

## ⚙️ 配置文件参数详解 (`config.json`)

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

关于上述各项参数的详细描述和更多高阶场景（如软路由内网 DNS 局域网解析）的配置模板，请阅读项目内置的 **[config_readme.md](file:///Users/qinzhanbo/Downloads/iptv/config_readme.md)**。

---

## 🐳 Docker Compose 一键部署

在您需要运行服务的机器上，将该项目的 5 个核心文件拉取到同一个目录下，执行以下命令即可：

```bash
# 1. 以后台守护进程模式构建并启动容器
docker compose up -d --build

# 2. 实时查看容器的运行日志（可看到下载、DoH解析和并发连接测速的过程）
docker compose logs -f
```

**目录挂载说明**：
容器启动后，会在当前宿主机目录下自动创建一个 `output` 文件夹。所有下载、解析、优选测速完毕后的 `.m3u` 或 `.txt` 节目源文件都将被保存在这个文件夹里。
您的其他 IPTV 播放端、xTeVe、Jellyfin、DIYP 接口等服务，可以直接将源指向宿主机上该文件夹下的解析后文件！

---

## 🛠️ 本地手动运行

如果您不想使用 Docker，也可直接通过 Python 3 手动运行该工具（脚本内置了依赖自动补齐机制，缺失时会自动尝试调用 `pip` 补齐所需依赖）：

```bash
# 执行单次解析测试
python3 iptv_resolver.py -c config.json
```
