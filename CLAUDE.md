# CLAUDE.md — 中国航班实时雷达

Flask + Leaflet.js 的中国空域航班实时追踪 Web 应用，数据来自 FlightRadar24 非官方 API。

## 启动

```bash
pip install flask flask-cors FlightRadarAPI
python app.py
# http://localhost:5000
```

或点击 `start_radar.bat`（Windows 一键启动）。

## 技术栈

- 后端：Flask（`app.py`），单文件 ~185 行
- 前端：Leaflet.js 1.9.4，单页应用（`templates/index.html`，~550 行 inline HTML/CSS/JS）
- 数据：FlightRadar24API SDK → `data-live.flightradar24.com`

## 架构要点

- **单体**：Flask 同时托管 API 和静态页面，无数据库，无外部缓存
- **内存缓存**：`_cache["data"]` + `_cache["timestamp"]`，TTL=8s，前端每 10s 轮询
- **重要**：此项目用 FR24 **非官方** API，注意请求频率（8s TTL 保守）
- **端口**：5000，绑定 `0.0.0.0`
- **宿主/端口探测**：`index.html:406` 检测 `window.location.port === '5500'`（Live Server dev），否则用相对路径

## 路由清单

| 路由 | 功能 |
|------|------|
| `GET /` | 返回 `templates/index.html` |
| `GET /api/flights` | 全量航班 JSON（含 `emergency` 字段） |
| `GET /api/flight/<icao24>` | 单航班查询 |
| `GET /api/stats` | 统计（按航司 Top10、高度分层） |
| `GET /api/airline_map` | 航司 IATA → 名称/国家（来自 `data/airline_map.json`） |
| `GET /api/aircraft_map` | 机型代码 → 名称/制造商（来自 `data/aircraft_map.json`） |

## 数据单位（前后端约定）

FR24 原始 → 转换 → API 输出：feet×0.3048→m, knots×1.852→km/h, fpm×0.00508→m/s。前端按 `baro_altitude` 着色（>10000m 红 / 3000-10000m 黄 / <3000m 绿 / 地面灰）。

## 文件

| 文件 | 职责 |
|------|------|
| `app.py` | Flask API、数据获取、缓存、紧急代码检测 |
| `templates/index.html` | 地图渲染、标记增量更新、详情面板、搜索/告警 |
| `start_radar.bat` | 一键启动脚本 |
| `airline_map.json` | 航司映射（`data/`） |
| `aircraft_map.json` | 机型映射（`data/`） |
| `TECHNICAL_DOCUMENTATION.md` | 详细技术文档（`docs/`） |
| `IMPROVEMENT_RECOMMENDATIONS.md` | 行业对比改进建议（`docs/`） |

## 红线

- 不要频繁请求 FR24 API（< 8s 间隔有封禁风险）
- 缓存降级已实现：API 异常时返回旧缓存避免断流
- 不要改 `origin_country` 字段名（实际是航司 IATA，已约定俗成）
- `index.html` 是生产模式（无构建步骤），不要引入 npm/webpack
