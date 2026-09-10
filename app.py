import os
import io
import uuid

# matplotlib needs a writable config dir on Vercel's read-only filesystem
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import psycopg2
import requests
from flask import Flask, Response, jsonify, render_template, request, send_file
from PIL import Image

app = Flask(__name__)

DATABASE_URL = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL")

AQI_LEVELS = [
    (50,  "Good",                              "#2ecc71", "Air quality is satisfactory. Enjoy outdoor activities freely."),
    (100, "Moderate",                          "#f1c40f", "Acceptable air quality. Unusually sensitive people should limit prolonged outdoor exertion."),
    (150, "Unhealthy for Sensitive Groups",    "#e67e22", "Children, elderly, and people with respiratory issues should reduce outdoor activity."),
    (200, "Unhealthy",                         "#e74c3c", "Everyone may start feeling effects. Limit outdoor exertion, wear a mask if going out."),
    (300, "Very Unhealthy",                    "#8e44ad", "Health alert. Avoid outdoor activity, keep windows closed, use an air purifier if possible."),
    (10**9, "Hazardous",                       "#7d1935", "Emergency conditions. Stay indoors, avoid all outdoor exposure."),
]

PALETTE = ["#5B8DEF", "#7ED6A5", "#FFC857", "#EF7674", "#B98CE0", "#5FD0C4", "#F2A65A"]

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


# ---------- DATABASE ----------
def get_connection():
    if not DATABASE_URL:
        raise RuntimeError(
            "POSTGRES_URL / DATABASE_URL is not set. "
            "Add a Postgres database to this project in the Vercel dashboard."
        )
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def init_db():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS records (
                    id TEXT PRIMARY KEY,
                    city TEXT NOT NULL,
                    date DATE NOT NULL,
                    aqi DOUBLE PRECISION,
                    pm25 DOUBLE PRECISION,
                    no2 DOUBLE PRECISION,
                    so2 DOUBLE PRECISION,
                    co DOUBLE PRECISION,
                    UNIQUE(city, date)
                );
            """)
        conn.commit()


_db_ready = False


def ensure_db():
    global _db_ready
    if not _db_ready:
        init_db()
        _db_ready = True


def load_dataset_df():
    ensure_db()
    with get_connection() as conn:
        df = pd.read_sql("SELECT * FROM records ORDER BY city, date;", conn)
    return df


def upsert_day(city, date_str, vals):
    ensure_db()
    record_id = str(uuid.uuid4())
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO records (id, city, date, aqi, pm25, no2, so2, co)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (city, date) DO UPDATE SET
                    aqi = EXCLUDED.aqi,
                    pm25 = EXCLUDED.pm25,
                    no2 = EXCLUDED.no2,
                    so2 = EXCLUDED.so2,
                    co = EXCLUDED.co
                RETURNING id;
            """, (record_id, city, date_str, vals["aqi"], vals["pm25"], vals["no2"], vals["so2"], vals["co"]))
            returned_id = cur.fetchone()[0]
        conn.commit()
    return returned_id


def delete_record_db(record_id):
    ensure_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM records WHERE id = %s;", (record_id,))
            deleted = cur.rowcount
        conn.commit()
    return deleted > 0


def aqi_info(aqi):
    if aqi is None or (isinstance(aqi, float) and np.isnan(aqi)):
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


# ---------- CHART RENDERING (in-memory, no disk writes) ----------
def render_chart_png(kind, raw_df):
    df = preprocess_data(raw_df)
    plt.figure(figsize=(10, 4.2))
    try:
        if df.empty:
            plt.text(0.5, 0.5, "No data yet — search a place first.",
                      ha="center", va="center", fontsize=12, color="#777")
            plt.axis("off")
        elif kind == "aqi_trends":
            trend_df = df.groupby(["city", "date"])["aqi"].mean().reset_index()
            for i, (city_name, group) in enumerate(trend_df.groupby("city")):
                group = group.sort_values("date")
                plt.plot(group["date"], group["aqi"], marker="o",
                         label=str(city_name), color=PALETTE[i % len(PALETTE)])
            plt.title("AQI Trend Across Cities")
            plt.xlabel("Date"); plt.ylabel("AQI")
            plt.legend(fontsize=8)
            plt.xticks(rotation=30)
        elif kind == "city_aqi_bar":
            city_summary = df.groupby("city")["aqi"].mean().sort_values()
            plt.barh(city_summary.index.astype(str), city_summary.values, color=PALETTE[0])
            plt.title("City-wise Average AQI")
            plt.xlabel("AQI")
        elif kind == "aqi_histogram":
            values = df["aqi"].dropna().values
            unique_count = len(set(values))
            bins = max(1, min(10, unique_count))
            plt.hist(values, bins=bins, color="#5B8DEF", edgecolor="white", linewidth=1.2, alpha=0.9)
            plt.title("AQI Distribution")
            plt.xlabel("AQI"); plt.ylabel("Frequency")
            plt.grid(True, axis="y", linestyle="--", alpha=0.5)
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150)
        buf.seek(0)
        return buf
    finally:
        plt.close()


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
    body = request.get_json(silent=True) or {}
    place_name = str(body.get("place", "")).strip()
    if not place_name:
        return jsonify({"error": "Please type a place name."}), 400

    geo = geocode_place(place_name)
    if not geo:
        return jsonify({"error": f"Couldn't find '{place_name}'. Try a nearby bigger town."}), 404

    historical = fetch_historical_aqi(geo["lat"], geo["lon"], days=7)
    if not historical:
        return jsonify({"error": "AQI data not available for this location right now."}), 404

    clean_name = geo["resolved_name"].strip().title()

    latest_id = None
    for day, vals in sorted(historical.items()):
        latest_id = upsert_day(clean_name, day, vals)

    latest_day = max(historical.keys())
    latest_vals = historical[latest_day]
    info = aqi_info(latest_vals["aqi"])

    return jsonify({
        "id": latest_id, "place": clean_name,
        "region": geo["admin1"], "country": geo["country"],
        "aqi": round(latest_vals["aqi"], 1) if latest_vals["aqi"] is not None else None,
        "status": info["status"], "color": info["color"], "advice": info["advice"],
        "pm25": latest_vals["pm25"], "no2": latest_vals["no2"],
        "so2": latest_vals["so2"], "co": latest_vals["co"],
        "days_added": len(historical),
    })


@app.route("/api/records", methods=["GET"])
def get_records():
    df = load_dataset_df()
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
    ok = delete_record_db(record_id)
    if not ok:
        return jsonify({"error": "Record not found."}), 404
    return jsonify({"deleted": True, "id": record_id})


@app.route("/api/chart-data")
def chart_data():
    df = preprocess_data(load_dataset_df())
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


# ---------- DOWNLOAD ROUTES (all generated in-memory, nothing written to disk) ----------
@app.route("/download/csv")
def download_csv():
    df = load_dataset_df()
    buf = io.BytesIO(df.to_csv(index=False).encode("utf-8"))
    return send_file(buf, mimetype="text/csv", as_attachment=True, download_name="air_pollution_data.csv")


@app.route("/download/excel")
def download_excel():
    df = load_dataset_df()
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True, download_name="air_pollution_data.xlsx",
    )


@app.route("/download/row/<record_id>")
def download_row(record_id):
    df = load_dataset_df()
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
    if chart_name not in ("aqi_trends", "city_aqi_bar", "aqi_histogram"):
        return jsonify({"error": "Unknown chart."}), 404
    df = load_dataset_df()
    if preprocess_data(df).empty:
        return jsonify({"error": "No charts found. Search a place first."}), 404
    png_buf = render_chart_png(chart_name, df)
    img = Image.open(png_buf).convert("RGB")
    pdf_buf = io.BytesIO()
    img.save(pdf_buf, format="PDF")
    pdf_buf.seek(0)
    return send_file(pdf_buf, mimetype="application/pdf",
                      as_attachment=True, download_name=f"{chart_name}.pdf")


@app.route("/download/all-charts-pdf")
def download_all_charts_pdf():
    df = load_dataset_df()
    if preprocess_data(df).empty:
        return jsonify({"error": "No charts found. Search a place first."}), 404
    chart_kinds = ["aqi_trends", "city_aqi_bar", "aqi_histogram"]
    images = [Image.open(render_chart_png(k, df)).convert("RGB") for k in chart_kinds]
    pdf_buf = io.BytesIO()
    first, rest = images[0], images[1:]
    first.save(pdf_buf, format="PDF", save_all=True, append_images=rest)
    pdf_buf.seek(0)
    return send_file(pdf_buf, mimetype="application/pdf",
                      as_attachment=True, download_name="all_charts.pdf")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
