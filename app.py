import os
import uuid
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import numpy as np
import pandas as pd
import requests
from flask import Flask, jsonify, render_template, request, send_file, Response
from PIL import Image

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(ROOT_DIR, "data", "air_pollution_data.csv")
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

app = Flask(__name__)

AQI_LEVELS = [
    (50,  "Good",                              "#2ecc71", "Air quality is satisfactory. Enjoy outdoor activities freely."),
    (100, "Moderate",                          "#f1c40f", "Acceptable air quality. Unusually sensitive people should limit prolonged outdoor exertion."),
    (150, "Unhealthy for Sensitive Groups",    "#e67e22", "Children, elderly, and people with respiratory issues should reduce outdoor activity."),
    (200, "Unhealthy",                         "#e74c3c", "Everyone may start feeling effects. Limit outdoor exertion, wear a mask if going out."),
    (300, "Very Unhealthy",                    "#8e44ad", "Health alert. Avoid outdoor activity, keep windows closed, use an air purifier if possible."),
    (10**9, "Hazardous",                       "#7d1935", "Emergency conditions. Stay indoors, avoid all outdoor exposure."),
]


def aqi_info(aqi):
    if aqi is None:
        return {"status": "Unknown", "color": "#999", "advice": "No data available."}
    for limit, status, color, advice in AQI_LEVELS:
        if aqi <= limit:
            return {"status": status, "color": color, "advice": advice}
    return {"status": "Hazardous", "color": "#7d1935", "advice": AQI_LEVELS[-1][3]}


def geocode_place(place_name):
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": place_name, "count": 1, "language": "en", "format": "json"}
    resp = requests.get(url, params=params, timeout=10)
    if resp.ok:
        results = resp.json().get("results")
        if results:
            top = results[0]
            return {
                "lat": top["latitude"], "lon": top["longitude"],
                "resolved_name": top.get("name"),
                "country": top.get("country", ""),
                "admin1": top.get("admin1", ""),
            }

    nom_url = "https://nominatim.openstreetmap.org/search"
    nom_params = {"q": place_name, "format": "json", "limit": 1, "addressdetails": 1}
    headers = {"User-Agent": "AirWatch-App/1.0"}
    nom_resp = requests.get(nom_url, params=nom_params, headers=headers, timeout=10)
    if nom_resp.ok:
        nom_results = nom_resp.json()
        if nom_results:
            top = nom_results[0]
            address = top.get("address", {})
            resolved_name = (
                address.get("village") or address.get("town") or
                address.get("city") or address.get("hamlet") or
                top.get("display_name", place_name).split(",")[0]
            )
            return {
                "lat": float(top["lat"]), "lon": float(top["lon"]),
                "resolved_name": resolved_name,
                "country": address.get("country", ""),
                "admin1": address.get("state", ""),
            }
    return None


def fetch_live_aqi(lat, lon):
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": "us_aqi,pm2_5,nitrogen_dioxide,sulphur_dioxide,carbon_monoxide",
        "timezone": "auto",
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    hourly = resp.json().get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        return None

    def latest_valid(lst):
        if not lst:
            return None
        for i in range(len(lst) - 1, -1, -1):
            if lst[i] is not None:
                return lst[i]
        return None

    aqi = latest_valid(hourly.get("us_aqi", []))
    if aqi is None:
        return None

    return {
        "aqi": aqi,
        "pm25": latest_valid(hourly.get("pm2_5", [])),
        "no2": latest_valid(hourly.get("nitrogen_dioxide", [])),
        "so2": latest_valid(hourly.get("sulphur_dioxide", [])),
        "co": latest_valid(hourly.get("carbon_monoxide", [])),
    }


def fetch_historical_aqi(lat, lon, days=7):
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": "us_aqi,pm2_5,nitrogen_dioxide,sulphur_dioxide,carbon_monoxide",
        "timezone": "auto",
        "past_days": days,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    hourly = resp.json().get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        return {}

    aqi_list = hourly.get("us_aqi", [])
    pm25_list = hourly.get("pm2_5", [])
    no2_list = hourly.get("nitrogen_dioxide", [])
    so2_list = hourly.get("sulphur_dioxide", [])
    co_list = hourly.get("carbon_monoxide", [])

    daily = {}
    for i, t in enumerate(times):
        day = t.split("T")[0]
        if day not in daily:
            daily[day] = {"aqi": [], "pm25": [], "no2": [], "so2": [], "co": []}
        if i < len(aqi_list) and aqi_list[i] is not None:
            daily[day]["aqi"].append(aqi_list[i])
        if i < len(pm25_list) and pm25_list[i] is not None:
            daily[day]["pm25"].append(pm25_list[i])
        if i < len(no2_list) and no2_list[i] is not None:
            daily[day]["no2"].append(no2_list[i])
        if i < len(so2_list) and so2_list[i] is not None:
            daily[day]["so2"].append(so2_list[i])
        if i < len(co_list) and co_list[i] is not None:
            daily[day]["co"].append(co_list[i])

    result = {}
    for day, vals in daily.items():
        if not vals["aqi"]:
            continue
        result[day] = {
            "aqi": sum(vals["aqi"]) / len(vals["aqi"]),
            "pm25": (sum(vals["pm25"]) / len(vals["pm25"])) if vals["pm25"] else None,
            "no2": (sum(vals["no2"]) / len(vals["no2"])) if vals["no2"] else None,
            "so2": (sum(vals["so2"]) / len(vals["so2"])) if vals["so2"] else None,
            "co": (sum(vals["co"]) / len(vals["co"])) if vals["co"] else None,
        }
    return result


def preprocess_data(df):
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if "city" in df.columns:
        df["city"] = df["city"].astype(str).str.strip()
    for col in ["aqi", "pm25", "no2", "so2", "co"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["city", "date", "aqi"]).copy()
    df = df.sort_values(["city", "date"]).reset_index(drop=True)
    return df


def load_dataset():
    if not os.path.exists(DATA_FILE):
        pd.DataFrame(columns=["id", "city", "date", "aqi", "pm25", "no2", "so2", "co"]).to_csv(DATA_FILE, index=False)
    df = pd.read_csv(DATA_FILE)
    if "id" not in df.columns:
        df["id"] = [str(uuid.uuid4()) for _ in range(len(df))]
        df.to_csv(DATA_FILE, index=False)
    else:
        missing = df["id"].isna()
        if missing.any():
            df.loc[missing, "id"] = [str(uuid.uuid4()) for _ in range(missing.sum())]
            df.to_csv(DATA_FILE, index=False)
    return df


# ---------- CHART STYLE ----------
plt.rcParams.update({
    "figure.facecolor": "#ffffff",
    "axes.facecolor": "#ffffff",
    "axes.edgecolor": "#d8dde3",
    "axes.labelcolor": "#333333",
    "axes.titlesize": 14,
    "axes.titleweight": "bold",
    "axes.titlecolor": "#1b1b1b",
    "xtick.color": "#555555",
    "ytick.color": "#555555",
    "grid.color": "#eef1f4",
    "font.family": "sans-serif",
})

PALETTE = ["#5B8DEF", "#7ED6A5", "#FFC857", "#EF7674", "#B98CE0", "#5FD0C4", "#F2A65A"]


def create_visualizations(df):
    df = preprocess_data(df)
    if df.empty:
        return

    try:
        trend_df = df.groupby(["city", "date"])["aqi"].mean().reset_index()
        plt.figure(figsize=(10, 4.2))
        for i, (city_name, group) in enumerate(trend_df.groupby("city")):
            group = group.sort_values("date")
            plt.plot(group["date"], group["aqi"], marker="o", linewidth=2.4,
                      markersize=6, label=city_name, color=PALETTE[i % len(PALETTE)])
        plt.title("AQI Trend Across Cities")
        plt.xlabel("Date"); plt.ylabel("AQI")
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.xticks(rotation=20)
        plt.legend(frameon=False)
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR, "aqi_trends.png"), dpi=150)
        plt.close()
    except Exception as e:
        print("Trend chart failed:", e)

    try:
        city_summary = df.groupby("city")["aqi"].mean().sort_values()
        colors = [PALETTE[i % len(PALETTE)] for i in range(len(city_summary))]
        plt.figure(figsize=(8, 4.2))
        bars = plt.bar(city_summary.index, city_summary.values, color=colors, edgecolor="white", linewidth=1.2)
        plt.title("Average AQI by City")
        plt.xlabel("City"); plt.ylabel("Average AQI")
        plt.grid(True, axis="y", linestyle="--", alpha=0.5)
        for b in bars:
            plt.text(b.get_x() + b.get_width() / 2, b.get_height() + 1,
                      f"{b.get_height():.0f}", ha="center", fontsize=9, color="#333")
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR, "city_aqi_bar.png"), dpi=150)
        plt.close()
    except Exception as e:
        print("City-wise chart failed:", e)

    try:
        values = df["aqi"].dropna().values
        unique_count = len(set(values))
        bins = max(1, min(10, unique_count))
        plt.figure(figsize=(8, 4.2))
        plt.hist(values, bins=bins, color="#5B8DEF", edgecolor="white", linewidth=1.2, alpha=0.9)
        plt.title("AQI Distribution")
        plt.xlabel("AQI"); plt.ylabel("Frequency")
        plt.grid(True, axis="y", linestyle="--", alpha=0.5)
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR, "aqi_histogram.png"), dpi=150)
        plt.close()
    except Exception as e:
        print("Histogram failed:", e)


# ---------- PAGE ROUTES ----------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/trend")
def trend_page():
    return render_template("trend.html")


@app.route("/citywise")
def citywise_page():
    return render_template("citywise.html")


@app.route("/distribution")
def distribution_page():
    return render_template("distribution.html")


@app.route("/downloads")
def downloads_page():
    return render_template("downloads.html")


# ---------- API ROUTES ----------
@app.route("/api/search", methods=["POST"])
def search_place():
    place_name = request.json.get("place", "").strip()
    if not place_name:
        return jsonify({"error": "Please type a place name."}), 400

    geo = geocode_place(place_name)
    if not geo:
        return jsonify({"error": f"Couldn't find '{place_name}'. Try a nearby bigger town."}), 404

    historical = fetch_historical_aqi(geo["lat"], geo["lon"], days=7)
    if not historical:
        return jsonify({"error": "AQI data not available for this location right now."}), 404

    clean_name = geo["resolved_name"].strip().title()
    df = load_dataset()

    for day, vals in sorted(historical.items()):
        match_mask = (
            (df["city"].astype(str).str.strip().str.lower() == clean_name.lower()) &
            (df["date"].astype(str).str.strip() == day)
        )
        if match_mask.any():
            df.loc[match_mask, "city"] = clean_name
            df.loc[match_mask, "aqi"] = vals["aqi"]
            df.loc[match_mask, "pm25"] = vals["pm25"]
            df.loc[match_mask, "no2"] = vals["no2"]
            df.loc[match_mask, "so2"] = vals["so2"]
            df.loc[match_mask, "co"] = vals["co"]
        else:
            new_row = {
                "id": str(uuid.uuid4()),
                "city": clean_name,
                "date": day,
                "aqi": vals["aqi"], "pm25": vals["pm25"], "no2": vals["no2"],
                "so2": vals["so2"], "co": vals["co"],
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    df.to_csv(DATA_FILE, index=False)
    create_visualizations(df)

    latest_day = max(historical.keys())
    latest_vals = historical[latest_day]
    info = aqi_info(latest_vals["aqi"])

    latest_mask = (
        (df["city"].astype(str).str.strip().str.lower() == clean_name.lower()) &
        (df["date"].astype(str).str.strip() == latest_day)
    )
    record_id = df.loc[latest_mask, "id"].iloc[0] if latest_mask.any() else str(uuid.uuid4())

    return jsonify({
        "id": record_id, "place": clean_name,
        "region": geo["admin1"], "country": geo["country"],
        "aqi": round(latest_vals["aqi"], 1) if latest_vals["aqi"] is not None else None,
        "status": info["status"], "color": info["color"], "advice": info["advice"],
        "pm25": latest_vals["pm25"], "no2": latest_vals["no2"],
        "so2": latest_vals["so2"], "co": latest_vals["co"],
        "days_added": len(historical),
    })


@app.route("/api/records", methods=["GET"])
def get_records():
    df = load_dataset()
    records = []
    for _, row in df.iterrows():
        info = aqi_info(row.get("aqi"))
        records.append({
            "id": row.get("id"), "city": row.get("city"), "date": str(row.get("date")),
            "aqi": row.get("aqi"), "pm25": row.get("pm25"), "no2": row.get("no2"),
            "so2": row.get("so2"), "co": row.get("co"),
            "status": info["status"], "color": info["color"],
        })
    return jsonify(records[::-1])


@app.route("/api/delete/<record_id>", methods=["DELETE"])
def delete_record(record_id):
    df = load_dataset()
    if record_id not in df["id"].values:
        return jsonify({"error": "Record not found."}), 404
    df = df[df["id"] != record_id]
    df.to_csv(DATA_FILE, index=False)
    create_visualizations(df)
    return jsonify({"deleted": True, "id": record_id})


@app.route("/api/chart-data")
def chart_data():
    df = preprocess_data(load_dataset())
    if df.empty:
        return jsonify({"trend": {}, "citywise": {}, "distribution": {}})

    trend = {}
    for city_name, group in df.groupby("city"):
        group = group.sort_values("date")
        trend[str(city_name)] = {
            "dates": [str(d) for d in group["date"].dt.strftime("%Y-%m-%d").tolist()],
            "aqi": [float(v) for v in group["aqi"].tolist()],
        }

    city_summary = df.groupby("city")["aqi"].mean().sort_values()
    citywise = {
        "cities": [str(c) for c in city_summary.index.tolist()],
        "values": [round(float(v), 1) for v in city_summary.values.tolist()],
    }

    values = df["aqi"].dropna().values
    unique_count = len(set(values))
    bins = max(1, min(10, unique_count))
    counts, edges = np.histogram(values, bins=bins)
    distribution = {
        "counts": [int(c) for c in counts.tolist()],
        "edges": [round(float(e), 1) for e in edges.tolist()],
    }

    return jsonify({"trend": trend, "citywise": citywise, "distribution": distribution})


@app.route("/output/<filename>")
def get_chart(filename):
    return send_file(os.path.join(OUTPUT_DIR, filename))


@app.route("/download/csv")
def download_csv():
    return send_file(DATA_FILE, as_attachment=True)


@app.route("/download/excel")
def download_excel():
    df = load_dataset()
    excel_path = os.path.join(OUTPUT_DIR, "air_pollution_data.xlsx")
    df.to_excel(excel_path, index=False)
    return send_file(excel_path, as_attachment=True)


@app.route("/download/row/<record_id>")
def download_row(record_id):
    df = load_dataset()
    row = df[df["id"] == record_id]
    if row.empty:
        return jsonify({"error": "Record not found."}), 404
    csv_data = row.to_csv(index=False)
    return Response(
        csv_data, mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={record_id}.csv"},
    )


@app.route("/download/chart-pdf/<chart_name>")
def download_chart_pdf(chart_name):
    png_path = os.path.join(OUTPUT_DIR, f"{chart_name}.png")
    if not os.path.exists(png_path):
        return jsonify({"error": "Chart not found. Search a place first."}), 404
    pdf_path = os.path.join(OUTPUT_DIR, f"{chart_name}.pdf")
    img = Image.open(png_path).convert("RGB")
    img.save(pdf_path)
    return send_file(pdf_path, as_attachment=True)


@app.route("/download/all-charts-pdf")
def download_all_charts_pdf():
    chart_files = ["aqi_trends.png", "city_aqi_bar.png", "aqi_histogram.png"]
    images = []
    for name in chart_files:
        path = os.path.join(OUTPUT_DIR, name)
        if os.path.exists(path):
            images.append(Image.open(path).convert("RGB"))

    if not images:
        return jsonify({"error": "No charts found. Search a place first."}), 404

    pdf_path = os.path.join(OUTPUT_DIR, "all_charts.pdf")
    first, rest = images[0], images[1:]
    first.save(pdf_path, save_all=True, append_images=rest)
    return send_file(pdf_path, as_attachment=True)

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)