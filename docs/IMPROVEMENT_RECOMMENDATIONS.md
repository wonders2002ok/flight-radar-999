# 改进建议报告 — 对比行业成熟项目

> **基准项目**: flight-radar-999 | **调研日期**: 2026-04-29  
> **调研范围**: GitHub 开源 ADS-B 项目、FlightRadar24 / ADSBExchange 等商业产品、行业最佳实践

---

## 调研概览

对 GitHub 上 **30+ 个 ADS-B 航班追踪开源项目**进行了横向对比，识别出当前项目与成熟方案之间的差距。核心参照物：**[wiedehopf/tar1090](https://github.com/wiedehopf/tar1090)**（1,625+ ⭐，被 ADSBExchange、adsb.lol 等大型聚合站采用）、**[ClickHouse/adsb.exposed](https://github.com/ClickHouse/adsb.exposed)**（大规模分析）、**[ISmillex/adsb-flight-map](https://github.com/ISmillex/adsb-flight-map)**（3D 可视化）、**[airspace-visualizer](https://github.com/mebrown47/airspace-visualizer)**（全方位雷达面板）。

---

## 改进建议总览

每个建议按 **价值/成本比** 和 **实施难度** 分为三个层级：

| 层级 | 含义 | 建议数量 |
|------|------|----------|
| **P0 — 必备** | 成熟项目的标配功能，缺失会显得产品简陋 | 5 |
| **P1 — 推荐** | 显著提升用户体验或技术架构，成熟项目普遍具备 | 6 |
| **P2 — 进阶** | 差异化特性，需要较多投入但能拉开差距 | 5 |

---

## P0 — 必备改进（价值极高，成本较低）

### 1. 🔴 紧急代码告警（Squawk Alert）

> **状态**：🟡 后端已完成（2026-04-30），前端告警 UI 待实施。

**参照项目**: tar1090, ADSBExchange, FlightRadar24, 几乎所有成熟追踪器

| Squawk | 含义 | 当前处理 |
|--------|------|----------|
| 7700 | Emergency（紧急情况） | 后端已检测，API 返回 `emergency` 字段 |
| 7600 | Radio Failure（无线电失效） | 后端已检测，API 返回 `emergency` 字段 |
| 7500 | Hijack（劫机） | 后端已检测，API 返回 `emergency` 字段 |

**已完成**：
- 后端 `fetch_flights_data()` 中检测 squawk 并设置 `emergency` 字段（app.py:74-76）

**待实施**：
- 前端地图上以闪烁/特殊图标高亮紧急航班
- 弹出显眼的通知（红色 Toast + 声音）
- 详情面板中显示紧急代码的中文释义

**成本**：约 30 行前端代码。

---

### 2. 🏷️ 航司/机型真实名称映射

> **状态**：🟡 数据层已完成（2026-04-30），前端集成待实施。

**参照项目**: tar1090-db, FlightRadar24, FlightAware

**已完成**：
- `airline_map.json` — 42 条航司 IATA → 中文名称 + 国家映射表
- `aircraft_map.json` — 100+ 条机型代码 → 名称 + 制造商 + 宽窄体分类
- `/api/airline_map` 和 `/api/aircraft_map` 端点已就绪

**待实施**：
- 前端调用映射 API 并格式化显示：`MU` → "中国东方航空 · 中国"
- 详情面板中将 `origin_country` + `category` 替换为映射后的中文名

**成本**：约 30 行前端代码。

---

### 3. 🎯 视口裁剪（Viewport Culling）

**参照项目**: tar1090, 所有成熟前端

**当前问题**：所有 500–600 架航班无论是否在可视范围内全部渲染成 DOM 节点，导致：
- 地图缩放至局部时仍然渲染远端几千公里外的飞机
- 高缩放级别下数百个不可见 marker 白白消耗性能
- 低性能设备可能出现明显卡顿

**建议**：
- 每次 `renderFlights()` 时检查航班经纬度是否在地图当前 bounds 内
- 只对可见航班创建/更新 marker
- 配合 `map.getBounds().contains()` 判断
- 可选：视野外的 marker 保留但不更新 DOM（冻结），视野内恢复

**成本**：约 20 行前端代码，改动集中在 `renderFlights()` 函数。

---

### 4. 🌐 航班轨迹线（Flight Trails）

**参照项目**: tar1090（8 小时历史轨迹）、ADSBExchange、FlightRadar24

**当前问题**：飞机在地图上只是孤立的位置点，看不到飞行路径。这是 flight radar 类产品最基本的视觉特征之一。

**建议**：
- 前端为每架飞机维护最近 N 个位置点的数组（如 20 个点，约 3 分钟轨迹）
- 用 Leaflet `L.polyline` 绘制半透明尾迹
- 颜色与飞机当前高度色一致
- 可选：后端保存轨迹数据到内存缓存

**成本**：约 50 行前端代码。

---

### 5. 🔍 航班搜索与筛选

**参照项目**: tar1090（正则表达式筛选）、FlightRadar24

**当前问题**：500+ 架飞机在图上，用户无法快速定位特定航班。tar1090 甚至支持正则表达式过滤（如 `B73.|A32.` 只看 737/A320 系列）。

**建议**：
- 顶部栏添加搜索框，支持按呼号搜索（输入 "CES5123" 自动定位并居中）
- 添加快速筛选按钮：仅显示空中/仅显示地面/按高度范围筛选
- 可选的进阶筛选：按机型正则过滤

**成本**：约 60 行前端代码。

---

## P1 — 推荐改进（价值高，成本中等）

### 6. 📡 WebSocket / SSE 实时推送

**参照项目**: AeroTrack, airspace-visualizer, 多数商业产品

**当前问题**：前端每 10 秒轮询一次，数据有 0–10 秒延迟。10 秒内的飞机位置跳跃不连续，不支持平滑动画。

**建议**：
- 使用 **Server-Sent Events (SSE)** 替代轮询——比 WebSocket 更轻量，无需额外库
- 方案 A（简单）：后端每 2 秒推送一次缓存数据，前端平滑插值过渡
- 方案 B（更好）：后端维持对 FR24 的持续请求，数据到达立即推送到前端
- 权衡：SSE 需要后端保持长连接，但 Flask 的同步模型可能成为瓶颈。可以考虑 FastAPI + asyncio 迁移

**成本**：方案 A 约 40 行改动；方案 B 涉及异步框架迁移，约 200 行。

---

### 7. 📊 时序统计图表（graphs1090 风格）

**参照项目**: [wiedehopf/graphs1090](https://github.com/wiedehopf/graphs1090) (409⭐), skystats

**当前问题**：`/api/stats` 只返回实时快照，没有历史趋势。graphs1090 会展示过去 8 小时的航班数量、信号覆盖、高度分布变化等时序图。

**建议**：
- 后端定期采样统计数据（每分钟），保存到轻量级内存队列（如 deque，保留最近 24 小时）
- 新增 `/api/stats/history` 端点返回时序数据
- 前端用 Chart.js 绘制：航班数量趋势、高度分布变化、按国家 Top 5 变化
- 放在单独的统计页或详情面板中

**成本**：引入 Chart.js CDN + 约 150 行前后端代码。

---

### 8. 🛡️ API 鉴权与限流

**参照项目**: OpenSky（OAuth2 + credits）、FlightRadar24（订阅制）

**当前问题**：API 完全开放，如果部署到公网可能被滥用，且所有请求都走 FR24 外部 API，没有保护机制。

**建议**：
- 添加简单的 API Key 认证（Header: `X-API-Key`）
- 后端请求限流：每 IP 每分钟最多 6 次 `/api/flights` 请求
- Flask-Limiter 库实现，2 行配置
- 对静态页面（`/`）不限流

**成本**：引入 `flask-limiter` + 约 20 行代码。

---

### 9. 🐳 Docker 化部署

**参照项目**: sdr-enthusiasts/docker-adsb-ultrafeeder (480⭐), ADSB-Ultrafeeder

**当前问题**：仅支持 Windows `.bat` 脚本启动，没有 Docker 支持。几乎所有成熟的 ADS-B 项目都提供 Docker Compose 一键部署。

**建议**：
- 编写 `Dockerfile`（基于 `python:3.11-slim`）
- 编写 `docker-compose.yml`
- 可选：预构建镜像推到 GitHub Container Registry
- 脚本文件内容不超过 30 行

**成本**：约 40 行配置文件。

---

### 10. 📱 移动端适配

**参照项目**: AeroTrack, FlightRadar24 App

**当前问题**：当前 UI 仅针对桌面设计，280px 宽的详情面板在小屏幕上遮挡地图。top-bar 在小屏幕上拥挤。

**建议**：
- 使用 CSS `@media (max-width: 768px)` 适配
- 移动端：详情面板改为底部滑出（bottom sheet），统计栏缩小/折叠
- 触摸优化：增加 marker 点击区域

**成本**：约 80 行 CSS。

---

### 11. 🗄️ 数据持久化（轻量级）

**参照项目**: ClickHouse/adsb.exposed（大数据分析）、tar1090（globe_history）

**当前问题**：完全没有数据存储，无法回溯历史、查看趋势、分析航班模式。

**建议**：
- 轻量方案：每小时落一份 JSON 快照到磁盘（或 SQLite），文件名含时间戳
- 保留最近 48 小时
- 新增 `/api/history?ts=1714400000` 端点
- 不引入重型数据库

**成本**：约 60 行后端代码，无额外依赖。

---

## P2 — 进阶改进（差异化特性，投入较大）

### 12. 🌍 3D 地球视图

**参照项目**: [ISmillex/adsb-flight-map](https://github.com/ISmillex/adsb-flight-map) (CesiumJS), globe.adsbexchange.com, planes.live

**建议**：
- 使用 CesiumJS 替代 Leaflet，渲染 3D 地球
- 飞机以 billboard 图标展示，带高度柱
- 相机动画飞向指定航班

**成本**：引入 CesiumJS（较重，需 API token）+ 重写整个渲染层（约 300–500 行）。属于重大架构变更，建议作为独立可选视图保留 2D 模式。

---

### 13. 🗺️ 自建数据接收能力（RTL-SDR + readsb）

**参照项目**: readsb, dump1090-fa, adsb.im (dirkhh/adsb-feeder-image)

**建议**：
- 支持从本地 `readsb`/`dump1090` 实例获取 JSON 数据
- 意味着用户可以用一个 100 元的 RTL-SDR 接收器 + 树莓派自建地面站
- 不需要依赖任何外部 API
- 可同时保留 FR24 API 作为备选数据源

**成本**：需要硬件（RTL-SDR），后端新增 readsb JSON 适配器（约 100 行）。对"自建站"用户群体有吸引力。

---

### 14. 🔗 多数据源聚合

**参照项目**: [ShadowBroker](https://github.com/bigbodycobain)（同时聚合 ADS-B + AIS + 卫星 + 地震等 15 个数据源）

**建议**：
- 同时聚合 FR24、OpenSky、本地 readsb 三个数据源
- 按 ICAO24 去重合并，优先采用更新时间最新的
- 某个数据源故障时自动降级
- 可以扩展到 AIS 船舶追踪（MarineTraffic API）

**成本**：约 200 行后端代码 + 数据合并去重逻辑。

---

### 15. 🤖 AI 智能分析（差异化特性）

**参照项目**: [airspace-visualizer](https://github.com/mebrown47/airspace-visualizer)（集成 Ollama 本地 LLM）

**建议**：
- 检测异常飞行模式（盘旋、返航、偏离航线）
- 识别特殊航班（专机、货机、军机）
- 航班延误预测
- 自然语言查询（"显示浦东机场上空的所有航班"）

**成本**：较高。需要 ML 模型或 LLM 集成 + 持续计算。airspace-visualizer 使用 Ollama 本地 LLM 做语义查询，是一个可行的起点。

---

### 16. 🖼️ 飞机照片集成

**参照项目**: FlightRadar24, ADSBExchange（集成 planespotters.net 照片）

**建议**：
- 根据飞机注册号调用 planespotters.net API 获取飞机真实照片
- 在详情面板中显示
- 注意：需要用户获取到注册号（当前 FR24 匿名 API 可能不返回此字段）

**成本**：中等，取决于能否拿到注册号数据。

---

## 横向对比矩阵

| 特性 | flight-radar-999 | tar1090 | FlightRadar24 | ADSBExchange |
|------|:---:|:---:|:---:|:---:|
| 实时地图 | ✅ | ✅ | ✅ | ✅ |
| 航向旋转图标 | ✅ | ✅ | ✅ | ✅ |
| 航班详情面板 | ✅ | ✅ | ✅ | ✅ |
| 高度着色 | ✅ | ✅ | ✅ | ✅ |
| **飞行轨迹线** | ❌ | ✅ | ✅ | ✅ |
| **视口裁剪** | ❌ | ✅ | ✅ | ✅ |
| **紧急代码告警** | ❌ | ✅ | ✅ | ✅ |
| **航班搜索/筛选** | ❌ | ✅ | ✅ | ✅ |
| **航司/机型映射** | ❌ | ✅ | ✅ | ✅ |
| **3D 地球视图** | ❌ | ⚠️ | ❌ | ✅ |
| **历史回放** | ❌ | ✅ | ✅ | ❌ |
| **时序统计图表** | ❌ | ✅ | ⚠️ | ⚠️ |
| **Dark 主题** | ✅ | ✅ | ✅ | ✅ |
| **Mobile 适配** | ❌ | ✅ | ✅ | ✅ |
| **WebSocket 推送** | ❌ | ❌ | ✅ | ✅ |
| **API 鉴权** | ❌ | ❌ | ✅ | ✅ |
| **Docker 部署** | ❌ | ✅ | ❌ | ✅ |
| **自建接收** | ❌ | ✅ | ✅ | ✅ |
| **多源聚合** | ❌ | ❌ | ❌ | ✅ |
| **数据库持久化** | ❌ | ✅ | ✅ | ✅ |

> ⚠️ = 部分支持 | ❌ = 缺失 | ✅ = 具备

---

## 建议实施路线图

```
Phase 1（1–2 天，P0 全做）
├── Squawk 紧急代码告警
├── 航司/机型名称映射
├── 视口裁剪
├── 航班轨迹线
└── 航班搜索筛选

Phase 2（3–5 天，选 3–4 个 P1）
├── 数据持久化（SQLite）
├── SSE 实时推送
├── Docker 部署
├── 移动端适配
├── 时序统计图表
└── API 鉴权限流

Phase 3（1–2 周，选 1–2 个 P2）
├── 3D 地球视图（CesiumJS）
├── 自建数据接收（RTL-SDR）
├── 多数据源聚合
└── AI 智能分析
```

---

## 关键开源项目速查

| 项目 | 地址 | 核心价值 |
|------|------|----------|
| **tar1090** | [github.com/wiedehopf/tar1090](https://github.com/wiedehopf/tar1090) | 最成熟的 ADS-B Web 前端，轨迹线/筛选/多选等 UI 模式可直接参考 |
| **readsb** | [github.com/wiedehopf/readsb](https://github.com/wiedehopf/readsb) | 自建接收标准解码器 |
| **graphs1090** | [github.com/wiedehopf/graphs1090](https://github.com/wiedehopf/graphs1090) | 时序统计图表设计参考 |
| **adsb.exposed** | [github.com/ClickHouse/adsb.exposed](https://github.com/ClickHouse/adsb.exposed) | 大规模 ADS-B 数据分析参考 |
| **adsb-flight-map** | [github.com/ISmillex/adsb-flight-map](https://github.com/ISmillex/adsb-flight-map) | CesiumJS 3D 航班追踪参考 |
| **airspace-visualizer** | [github.com/mebrown47/airspace-visualizer](https://github.com/mebrown47/airspace-visualizer) | AI + ADS-B 集成参考 |
| **FlightRadarAPI** | [github.com/JeanExtreme002/FlightRadarAPI](https://github.com/JeanExtreme002/FlightRadarAPI) | 当前项目使用的 FR24 SDK |
| **Flight-Radar** | [github.com/U-C4N/Flight-Radar](https://github.com/U-C4N/Flight-Radar) | 同类型 Flask 项目，多语言支持参考 |
| **adsb-ultrafeeder** | [github.com/sdr-enthusiasts/docker-readsb-protobuf](https://github.com/sdr-enthusiasts/docker-readsb-protobuf) | Docker 全栈部署参考 |

---

> **结论**：当前项目在核心可视化层面已经达到可用水平（地图、图标、详情面板），但在飞行雷达的"标准功能集"方面有 5 个明显的缺失（P0）。建议先补齐 P0 的 5 项，可以使产品体验接近 tar1090 等成熟开源方案的水平，总投入约 1–2 天。
