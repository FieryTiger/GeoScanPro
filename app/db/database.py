import sqlite3
import json
from pathlib import Path
from datetime import datetime


DB_PATH = Path(__file__).parent.parent.parent / "geoscanpro.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS analyses (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT NOT NULL,
                scene_name      TEXT,
                ndwi_threshold  REAL,
                mndwi_threshold REAL,
                awei_threshold  REAL,
                lswi_threshold  REAL,
                min_object_size INTEGER,
                apply_morphology INTEGER,
                total_water_area_km2    REAL,
                total_water_area_pixels INTEGER,
                total_perimeter_km      REAL,
                water_percentage        REAL,
                object_count            INTEGER,
                largest_object_area     REAL,
                average_object_size     REAL,
                export_path             TEXT
            );

            CREATE TABLE IF NOT EXISTS water_objects (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
                object_idx  INTEGER,
                area_km2    REAL,
                area_pixels INTEGER,
                perimeter_km REAL,
                shape_factor REAL
            );
        """)


def save_analysis(results: dict, params: dict, scene_name: str, export_path: str = "") -> int:
    thresholds = params.get('thresholds', {})
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO analyses (
                timestamp, scene_name,
                ndwi_threshold, mndwi_threshold, awei_threshold, lswi_threshold,
                min_object_size, apply_morphology,
                total_water_area_km2, total_water_area_pixels, total_perimeter_km,
                water_percentage, object_count, largest_object_area, average_object_size,
                export_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            scene_name,
            thresholds.get('NDWI', 0.3),
            thresholds.get('MNDWI', 0.2),
            thresholds.get('AWEI_nsh', 0.0),
            thresholds.get('LSWI', 0.3),
            params.get('min_object_size', 100),
            int(params.get('apply_morphology', True)),
            results.get('total_water_area_km2', 0),
            results.get('total_water_area_pixels', 0),
            results.get('total_perimeter_km', 0),
            results.get('water_percentage', 0),
            results.get('object_count', 0),
            results.get('largest_object_area', 0),
            results.get('average_object_size', 0),
            export_path
        ))
        analysis_id = cursor.lastrowid

        objects = results.get('objects_data', [])
        for obj in objects:
            conn.execute("""
                INSERT INTO water_objects (analysis_id, object_idx, area_km2, area_pixels, perimeter_km, shape_factor)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                analysis_id,
                obj['id'],
                obj['area_km2'],
                obj['area_pixels'],
                obj['perimeter_km'],
                obj['shape_factor']
            ))

        return analysis_id


def get_all_analyses():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, timestamp, scene_name, water_percentage,
                   total_water_area_km2, object_count, export_path
            FROM analyses
            ORDER BY id DESC
        """).fetchall()
    return [dict(r) for r in rows]


def get_analysis_detail(analysis_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
        objects = conn.execute(
            "SELECT * FROM water_objects WHERE analysis_id = ? ORDER BY area_km2 DESC",
            (analysis_id,)
        ).fetchall()
    return dict(row) if row else None, [dict(o) for o in objects]


def delete_analysis(analysis_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM analyses WHERE id = ?", (analysis_id,))
