"""
中国航班实时雷达 - Flask 后端
数据来源：FlightRadar24 (非官方 API)
"""

import sys
import io
# Windows GBK 编码修复
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import time
import json
import logging
from pathlib import Path
from flask import Flask, jsonify
from flask_cors import CORS
from FlightRadar24 import FlightRadar24API

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FR24 API 实例
fr_api = FlightRadar24API()

# 中国空域边界框
CHINA_BOUNDS = {
    "lamin": 15.0,   # 南海诸岛
    "lamax": 55.0,   # 东北边境
    "lomin": 70.0,   # 西部边境
    "lomax": 140.0,  # 东海
}

# 缓存机制：避免频繁请求被封禁 (限制 8 秒刷新一次)
_cache = {"data": None, "timestamp": 0}
CACHE_TTL = 8

def fetch_flights_data():
    """从 FlightRadar24 API 获取中国空域实时航班数据"""
    now = time.time()
    
    # 使用缓存
    if _cache["data"] and (now - _cache["timestamp"]) < CACHE_TTL:
        return _cache["data"]
    
    try:
        bounds = fr_api.get_bounds({
            "tl_y": CHINA_BOUNDS["lamax"], 
            "tl_x": CHINA_BOUNDS["lomin"], 
            "br_y": CHINA_BOUNDS["lamin"], 
            "br_x": CHINA_BOUNDS["lomax"]
        })
        
        fr_flights = fr_api.get_flights(bounds=bounds)
        flights = []
        
        for f in fr_flights:
            # 兼容前端期望的数据结构
            # FR24 的 altitude 是英尺(feet)，需转换为米(m): feet * 0.3048
            # FR24 的 ground_speed 是节(knots)，需转换为 km/h: knots * 1.852
            # FR24 的 vertical_speed 是英尺/分钟(fpm)，需转换为 m/s: fpm * 0.00508
            
            icao24 = f.icao_24bit if f.icao_24bit else f.id
            callsign = f.callsign if f.callsign else "N/A"
            origin_country = f.airline_iata if f.airline_iata else "未知"
            
            baro_altitude = round(f.altitude * 0.3048, 1) if f.altitude is not None else None
            velocity = round(f.ground_speed * 1.852, 1) if f.ground_speed is not None else None
            vertical_rate = round(f.vertical_speed * 0.00508, 1) if f.vertical_speed is not None else None

            raw_squawk = f.squawk if f.squawk else None
            emergency = None
            if raw_squawk in ("7700", "7600", "7500"):
                emergency = raw_squawk

            flights.append({
                "icao24": icao24.lower(),
                "callsign": callsign,
                "origin_country": origin_country,
                "longitude": round(f.longitude, 4),
                "latitude": round(f.latitude, 4),
                "baro_altitude": baro_altitude,
                "on_ground": bool(f.on_ground),
                "velocity": velocity,
                "true_track": f.heading if f.heading is not None else 0,
                "vertical_rate": vertical_rate,
                "geo_altitude": baro_altitude,
                "squawk": raw_squawk,
                "emergency": emergency,
                "category": f.aircraft_code,
            })
            
        result = {
            "time": int(now),
            "count": len(flights),
            "flights": flights,
        }
        
        _cache["data"] = result
        _cache["timestamp"] = now
        logger.info(f"获取到 {len(flights)} 架航班数据 (FR24)")
        return result
        
    except Exception as e:
        logger.error(f"FlightRadar24 API 请求失败: {e}")
        if _cache["data"]:
            return _cache["data"]
        return {"time": int(now), "count": 0, "flights": [], "error": str(e)}

@app.route("/api/flights")
def get_flights():
    """获取实时航班数据"""
    data = fetch_flights_data()
    return jsonify(data)

@app.route("/api/flight/<icao24>")
def get_flight(icao24):
    """获取单架航班详情"""
    data = fetch_flights_data()
    for f in data.get("flights", []):
        if f["icao24"] == icao24.lower():
            return jsonify(f)
    return jsonify({"error": "航班未找到"}), 404

@app.route("/api/stats")
def get_stats():
    """获取统计信息"""
    data = fetch_flights_data()
    flights = data.get("flights", [])
    
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
    return Path("templates/index.html").read_text(encoding="utf-8")

@app.route("/api/airline_map")
def airline_map():
    """航司 IATA → 名称映射"""
    data = json.loads(Path("data/airline_map.json").read_text(encoding="utf-8"))
    return jsonify(data)

@app.route("/api/aircraft_map")
def aircraft_map():
    """机型代码 → 名称映射"""
    data = json.loads(Path("data/aircraft_map.json").read_text(encoding="utf-8"))
    return jsonify(data)

if __name__ == "__main__":
    print("🛫 中国航班实时雷达启动中...")
    print(f"   数据源: FlightRadar24 (非官方 API)")
    print(f"   覆盖范围: N{CHINA_BOUNDS['lamin']}-{CHINA_BOUNDS['lamax']}, E{CHINA_BOUNDS['lomin']}-{CHINA_BOUNDS['lomax']}")
    print(f"   访问地址: http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
