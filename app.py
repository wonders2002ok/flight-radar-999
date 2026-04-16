"""
中国航班实时雷达 - Flask 后端
数据来源：OpenSky Network API (ADS-B)
"""

import sys
import io
# Windows GBK 编码修复
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import time
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenSky API 配置
OPENSKY_API = "https://opensky-network.org/api/states/all"
# 中国空域边界框（后端过滤用，因为匿名用户带 bbox 参数会返回 null）
CHINA_BOUNDS = {
    "lamin": 15.0,   # 南海诸岛
    "lamax": 55.0,   # 东北边境
    "lomin": 70.0,   # 西部边境
    "lomax": 140.0,  # 东海
}

# 缓存机制：避免频繁请求 API
_cache = {"data": None, "timestamp": 0}
CACHE_TTL = 10  # 缓存10秒


def fetch_opensky_data():
    """从 OpenSky API 获取中国空域航班数据"""
    now = time.time()
    
    # 使用缓存
    if _cache["data"] and (now - _cache["timestamp"]) < CACHE_TTL:
        return _cache["data"]
    
    try:
        # 匿名用户不带 bbox 参数（带 bbox 会返回 null），全局请求后后端过滤
        resp = requests.get(OPENSKY_API, timeout=20)
        resp.raise_for_status()
        raw = resp.json()
        
        states = raw.get("states") or []
        flights = []
        
        for s in states:
            try:
                longitude = s[5]
                latitude = s[6]
                
                # 先做位置过滤：只保留中国空域
                if longitude is None or latitude is None:
                    continue
                if not (CHINA_BOUNDS["lamin"] <= latitude <= CHINA_BOUNDS["lamax"] and
                        CHINA_BOUNDS["lomin"] <= longitude <= CHINA_BOUNDS["lomax"]):
                    continue
                
                icao24 = s[0] or ""
                callsign = (s[1] or "").strip()
                origin_country = s[2] or ""
                baro_altitude = s[7]
                on_ground = s[8] if len(s) > 8 else False
                velocity = s[9]
                true_track = s[10]
                vertical_rate = s[11] if len(s) > 11 else None
                geo_altitude = s[13] if len(s) > 13 else None
                squawk = s[14] if len(s) > 14 else None
                category = s[17] if len(s) > 17 else None
                
                flights.append({
                    "icao24": icao24,
                    "callsign": callsign,
                    "origin_country": origin_country,
                    "longitude": round(longitude, 4),
                    "latitude": round(latitude, 4),
                    "baro_altitude": round(baro_altitude, 1) if baro_altitude else None,
                    "on_ground": on_ground,
                    "velocity": round(velocity * 3.6, 1) if velocity else None,  # m/s → km/h
                    "true_track": round(true_track, 1) if true_track else None,
                    "vertical_rate": round(vertical_rate, 1) if vertical_rate else None,
                    "geo_altitude": round(geo_altitude, 1) if geo_altitude else None,
                    "squawk": squawk,
                    "category": category,
                })
            except (IndexError, TypeError):
                continue
        
        result = {
            "time": raw.get("time", int(now)),
            "count": len(flights),
            "flights": flights,
        }
        
        _cache["data"] = result
        _cache["timestamp"] = now
        logger.info(f"获取到 {len(flights)} 架航班数据")
        return result
        
    except requests.exceptions.RequestException as e:
        logger.error(f"OpenSky API 请求失败: {e}")
        # 返回缓存数据（即使过期）
        if _cache["data"]:
            return _cache["data"]
        return {"time": int(now), "count": 0, "flights": [], "error": str(e)}


@app.route("/api/flights")
def get_flights():
    """获取中国空域实时航班数据"""
    data = fetch_opensky_data()
    return jsonify(data)


@app.route("/api/flight/<icao24>")
def get_flight(icao24):
    """获取单架航班详情"""
    data = fetch_opensky_data()
    for f in data.get("flights", []):
        if f["icao24"] == icao24.lower():
            return jsonify(f)
    return jsonify({"error": "航班未找到"}), 404


@app.route("/api/stats")
def get_stats():
    """获取统计信息"""
    data = fetch_opensky_data()
    flights = data.get("flights", [])
    
    # 按国家统计
    countries = {}
    altitude_ranges = {"地面": 0, "低空(<3000m)": 0, "中空(3000-8000m)": 0, "高空(8000-12000m)": 0, "超高(>12000m)": 0}
    
    for f in flights:
        country = f["origin_country"]
        countries[country] = countries.get(country, 0) + 1
        
        alt = f.get("baro_altitude")
        if f.get("on_ground") or alt is None:
            altitude_ranges["地面"] += 1
        elif alt < 3000:
            altitude_ranges["低空(<3000m)"] += 1
        elif alt < 8000:
            altitude_ranges["中空(3000-8000m)"] += 1
        elif alt < 12000:
            altitude_ranges["高空(8000-12000m)"] += 1
        else:
            altitude_ranges["超高(>12000m)"] += 1
    
    # 按数量排序国家
    top_countries = sorted(countries.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return jsonify({
        "total": len(flights),
        "top_countries": [{"country": c, "count": n} for c, n in top_countries],
        "altitude_ranges": altitude_ranges,
        "cache_age": round(time.time() - _cache["timestamp"], 1),
    })


@app.route("/")
def index():
    """前端页面"""
    from pathlib import Path
    return Path("index.html").read_text(encoding="utf-8")


if __name__ == "__main__":
    print("🛫 中国航班实时雷达启动中...")
    print(f"   数据源: OpenSky Network (ADS-B)")
    print(f"   覆盖范围: N{CHINA_BOUNDS['lamin']}-{CHINA_BOUNDS['lamax']}, E{CHINA_BOUNDS['lomin']}-{CHINA_BOUNDS['lomax']}")
    print(f"   访问地址: http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
