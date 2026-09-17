"""Sentinel-2 Raster Processing, Resampling, Window Tiling, and Vectorization."""

import asyncio
from io import BytesIO
import math
from typing import Any, Dict, List, Optional, Tuple
import cv2
import httpx
import numpy as np
import tifffile
import torch

from backend.app.core.errors import SatelliteBandReadError
from backend.app.schemas.satellite import (
    InundationGeoJsonFeature,
    InundationGeoJsonResponse,
    InundationPolygonGeometry,
    InundationPolygonProperties,
    Sentinel2SceneMetadata,
)
from backend.app.services.model2_service import Model2Service

REQUIRED_BAND_ORDER: List[str] = ["B2", "B3", "B4", "B8", "B11", "B12"]


# ============================================================
# GEODESIC & UTM TRANSFORM UTILITIES
# ============================================================

def latlon_to_utm(lat: float, lon: float, zone: Optional[int] = None, north: bool = True) -> Tuple[float, float, int]:
    """
    Project WGS84 geographic coordinates (lat, lon) to UTM coordinates (Easting, Northing).
    Snyder/Karney formulation on WGS84 ellipsoid.
    """
    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = 2.0 * f - f ** 2
    e_prime2 = e2 / (1.0 - e2)

    if zone is None:
        zone = int((lon + 180.0) / 6.0) + 1
    lon_origin = (zone - 1) * 6 - 180 + 3
    lon_origin_rad = math.radians(lon_origin)

    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)

    k0 = 0.9996
    N = a / math.sqrt(1.0 - e2 * math.sin(lat_rad) ** 2)
    T = math.tan(lat_rad) ** 2
    C = e_prime2 * math.cos(lat_rad) ** 2
    A = math.cos(lat_rad) * (lon_rad - lon_origin_rad)

    M = a * (
        (1.0 - e2 / 4.0 - 3.0 * e2 ** 2 / 64.0 - 5.0 * e2 ** 3 / 256.0) * lat_rad
        - (3.0 * e2 / 8.0 + 3.0 * e2 ** 2 / 32.0 + 45.0 * e2 ** 3 / 1024.0) * math.sin(2.0 * lat_rad)
        + (15.0 * e2 ** 2 / 256.0 + 45.0 * e2 ** 3 / 1024.0) * math.sin(4.0 * lat_rad)
        - (35.0 * e2 ** 3 / 3072.0) * math.sin(6.0 * lat_rad)
    )

    easting = k0 * N * (
        A + (1.0 - T + C) * A ** 3 / 6.0
        + (5.0 - 18.0 * T + T ** 2 + 72.0 * C - 58.0 * e_prime2) * A ** 5 / 120.0
    ) + 500000.0

    northing = k0 * (
        M + N * math.tan(lat_rad) * (
            A ** 2 / 2.0
            + (5.0 - T + 9.0 * C + 4.0 * C ** 2) * A ** 4 / 24.0
            + (61.0 - 58.0 * T + T ** 2 + 600.0 * C - 330.0 * e_prime2) * A ** 6 / 720.0
        )
    )
    if not north:
        northing += 10000000.0

    return easting, northing, zone


def utm_to_latlon(easting: float, northing: float, zone: int, north: bool = True) -> Tuple[float, float]:
    """
    Convert UTM coordinates (Easting, Northing) back to WGS84 geographic coordinates (lat, lon).
    """
    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = 2.0 * f - f ** 2
    e_prime2 = e2 / (1.0 - e2)
    e1 = (1.0 - math.sqrt(1.0 - e2)) / (1.0 + math.sqrt(1.0 - e2))

    k0 = 0.9996
    x = easting - 500000.0
    y = northing if north else northing - 10000000.0

    M = y / k0
    mu = M / (a * (1.0 - e2 / 4.0 - 3.0 * e2 ** 2 / 64.0 - 5.0 * e2 ** 3 / 256.0))

    phi1_rad = (
        mu
        + (3.0 * e1 / 2.0 - 27.0 * e1 ** 3 / 32.0) * math.sin(2.0 * mu)
        + (21.0 * e1 ** 2 / 16.0 - 55.0 * e1 ** 4 / 32.0) * math.sin(4.0 * mu)
        + (151.0 * e1 ** 3 / 96.0) * math.sin(6.0 * mu)
    )

    N1 = a / math.sqrt(1.0 - e2 * math.sin(phi1_rad) ** 2)
    T1 = math.tan(phi1_rad) ** 2
    C1 = e_prime2 * math.cos(phi1_rad) ** 2
    R1 = a * (1.0 - e2) / ((1.0 - e2 * math.sin(phi1_rad) ** 2) ** 1.5)
    D = x / (N1 * k0)

    lat = phi1_rad - (N1 * math.tan(phi1_rad) / R1) * (
        D ** 2 / 2.0
        - (5.0 + 3.0 * T1 + 10.0 * C1 - 4.0 * C1 ** 2 - 9.0 * e_prime2) * D ** 4 / 24.0
        + (61.0 + 90.0 * T1 + 298.0 * C1 + 45.0 * T1 ** 2 - 252.0 * e_prime2 - 3.0 * C1 ** 2) * D ** 6 / 720.0
    )

    lon_origin = (zone - 1) * 6 - 180 + 3
    lon = math.radians(lon_origin) + (
        D
        - (1.0 + 2.0 * T1 + C1) * D ** 3 / 6.0
        + (5.0 - 2.0 * C1 + 28.0 * T1 - 3.0 * C1 ** 2 + 8.0 * e_prime2 + 24.0 * T1 ** 2) * D ** 5 / 120.0
    ) / math.cos(phi1_rad)

    return math.degrees(lat), math.degrees(lon)


def parse_crs_to_utm_zone(crs_code: str, fallback_lon: float, fallback_lat: float) -> Tuple[int, bool]:
    """Parse EPSG code to determine UTM zone and hemisphere."""
    if crs_code and crs_code.upper().startswith("EPSG:"):
        try:
            code = int(crs_code.split(":")[1])
            if 32601 <= code <= 32660:
                return code - 32600, True
            elif 32701 <= code <= 32760:
                return code - 32700, False
        except (ValueError, IndexError):
            pass
    zone = int((fallback_lon + 180.0) / 6.0) + 1
    north = fallback_lat >= 0.0
    return zone, north


# ============================================================
# SENTINEL-2 RASTER PROCESSOR
# ============================================================

class SentinelRasterProcessor:
    """
    Coordinates reading Cloud-Optimized GeoTIFF (COG) band assets via HTTP Range requests,
    resampling 20m bands to 10m common grid, running windowed Model 2 inference,
    reconstructing probability mosaics, and polygonizing inundation masks into GeoJSON.
    """

    @staticmethod
    def resample_20m_to_10m(band_20m: np.ndarray, target_shape: Tuple[int, int] = (1024, 1024)) -> np.ndarray:
        """
        Resample 20m band to 10m grid using bilinear interpolation.
        Preserves reflectance magnitude and smooth gradients.
        """
        if band_20m.shape == target_shape:
            return band_20m.astype(np.float32)
        # cv2.resize expects (width, height)
        target_w, target_h = target_shape[1], target_shape[0]
        resampled = cv2.resize(band_20m.astype(np.float32), (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        return resampled

    async def fetch_cog_band_aligned(
        self,
        client: httpx.AsyncClient,
        url: str,
        band_name: str,
        col_10m: int,
        row_10m: int,
    ) -> np.ndarray:
        """
        Download and decode a band tile, dynamically aligning to the common 10m grid (1024x1024).
        Detects native COG tile width, height, and pixel scale from headers:
        - If tile_extent is ~10,240m (10m bands at 1024x1024, or 20m bands at 512x512):
          uses (row_10m, col_10m) directly.
        - If tile_extent is ~20,480m (20m bands at 1024x1024):
          reads quadrant (row_10m // 2, col_10m // 2) and slices 512x512 subwindow.
        Resamples all bands to exact (1024, 1024) output.
        """
        try:
            # 1. Read first 64KB for GeoTIFF tags
            hdr_resp = await client.get(url, headers={"Range": "bytes=0-65535"})
            if hdr_resp.status_code not in (200, 206):
                raise SatelliteBandReadError(
                    f"Failed to read COG header for band {band_name}: HTTP {hdr_resp.status_code}",
                    details={"band": band_name, "url": url},
                )

            with tifffile.TiffFile(BytesIO(hdr_resp.content)) as tif:
                page = tif.pages[0]
                scale = float(page.tags["ModelPixelScaleTag"].value[0])
                tile_w, tile_h = page.tilewidth, page.tilelength
                offsets = page.tags["TileOffsets"].value
                byte_counts = page.tags["TileByteCounts"].value

            tile_extent_m = tile_w * scale

            if abs(tile_extent_m - 10240.0) < 10.0:
                # 1-to-1 tile correspondence with 10m grid
                tile_idx = row_10m * 11 + col_10m
                tile_idx = min(tile_idx, len(offsets) - 1)
                tile_offset = int(offsets[tile_idx])
                tile_bytes_count = int(byte_counts[tile_idx])

                range_hdr = {"Range": f"bytes={tile_offset}-{tile_offset + tile_bytes_count - 1}"}
                tile_resp = await client.get(url, headers=range_hdr)
                if tile_resp.status_code not in (200, 206):
                    raise SatelliteBandReadError(
                        f"Failed to download tile {tile_idx} for band {band_name}: HTTP {tile_resp.status_code}",
                    )

                with tifffile.TiffFile(BytesIO(hdr_resp.content)) as tif:
                    decoded = tif.pages[0].decode(tile_resp.content, tile_idx)[0].squeeze()

                if decoded.shape != (1024, 1024):
                    decoded = cv2.resize(decoded.astype(np.float32), (1024, 1024), interpolation=cv2.INTER_LINEAR)
                return decoded.astype(np.float32)

            else:
                # 2x2 tile coverage (e.g. 20m band with 1024x1024 tile size = 20,480m)
                r_20m = row_10m // 2
                c_20m = col_10m // 2
                tile_idx = r_20m * 6 + c_20m
                tile_idx = min(tile_idx, len(offsets) - 1)
                tile_offset = int(offsets[tile_idx])
                tile_bytes_count = int(byte_counts[tile_idx])

                range_hdr = {"Range": f"bytes={tile_offset}-{tile_offset + tile_bytes_count - 1}"}
                tile_resp = await client.get(url, headers=range_hdr)
                if tile_resp.status_code not in (200, 206):
                    raise SatelliteBandReadError(
                        f"Failed to download 20m tile {tile_idx} for band {band_name}: HTTP {tile_resp.status_code}",
                    )

                with tifffile.TiffFile(BytesIO(hdr_resp.content)) as tif:
                    raw_tile = tif.pages[0].decode(tile_resp.content, tile_idx)[0].squeeze()

                delta_r = (row_10m % 2) * 512
                delta_c = (col_10m % 2) * 512
                sub_quadrant = raw_tile[delta_r : delta_r + 512, delta_c : delta_c + 512]
                resampled = cv2.resize(sub_quadrant.astype(np.float32), (1024, 1024), interpolation=cv2.INTER_LINEAR)
                return resampled.astype(np.float32)

        except Exception as exc:
            if isinstance(exc, SatelliteBandReadError):
                raise
            raise SatelliteBandReadError(
                f"Error processing COG tile for band {band_name}: {exc}",
                details={"band": band_name, "error": str(exc)},
            ) from exc

    async def fetch_and_align_scene(
        self,
        scene: Sentinel2SceneMetadata,
        query_lat: float,
        query_lon: float,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Identify geographic tile enclosing (query_lat, query_lon),
        fetch 6 required bands in parallel, resample 20m bands,
        and assemble a (6, 1024, 1024) common grid float32 array.
        """
        zone, north = parse_crs_to_utm_zone(scene.crs, query_lon, query_lat)
        query_easting, query_northing, _ = latlon_to_utm(query_lat, query_lon, zone=zone, north=north)

        # Sentinel-2 Level-2A COGs on AWS have top-left tiepoint origin
        b2_url = scene.band_assets["B2"].asset_url
        async with httpx.AsyncClient(timeout=30.0) as client:
            hdr_resp = await client.get(b2_url, headers={"Range": "bytes=0-65535"})
            with tifffile.TiffFile(BytesIO(hdr_resp.content)) as tif:
                p2 = tif.pages[0]
                tiepoint = p2.tags["ModelTiepointTag"].value
                pixel_scale = p2.tags["ModelPixelScaleTag"].value
                x0 = float(tiepoint[3])
                y0 = float(tiepoint[4])
                scale_10m = float(pixel_scale[0])

            # Calculate tile row and column in 10m grid (each tile is 1024x1024)
            col_10m = int((query_easting - x0) / (1024.0 * scale_10m))
            row_10m = int((y0 - query_northing) / (1024.0 * scale_10m))

            # Clamp within valid granule tile bounds (11 x 11 tiles)
            col_10m = max(0, min(10, col_10m))
            row_10m = max(0, min(10, row_10m))

            # Tile geographic top-left corner
            tile_origin_x = x0 + (col_10m * 1024) * scale_10m
            tile_origin_y = y0 - (row_10m * 1024) * scale_10m

            # Fetch 6 bands in parallel
            tasks = []
            for band_name in REQUIRED_BAND_ORDER:
                asset = scene.band_assets[band_name]
                tasks.append(
                    self.fetch_cog_band_aligned(client, asset.asset_url, band_name, col_10m, row_10m)
                )

            aligned_bands = await asyncio.gather(*tasks)

        # Stack into [6, 1024, 1024]
        stacked_tensor = np.stack(aligned_bands, axis=0).astype(np.float32)

        grid_metadata = {
            "origin_x": tile_origin_x,
            "origin_y": tile_origin_y,
            "pixel_scale_m": 10.0,
            "utm_zone": zone,
            "utm_north": north,
            "crs": scene.crs,
            "width": 1024,
            "height": 1024,
            "tile_row": row_10m,
            "tile_col": col_10m,
        }

        return stacked_tensor, grid_metadata

    def tile_and_predict(
        self,
        raster_data: np.ndarray,
        model2_service: Model2Service,
        window_size: int = 512,
        overlap: int = 64,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Split common grid raster [6, H, W] into 512x512 windows with overlap,
        run Model 2 inference for each tile, reconstruct full probability mosaic,
        and threshold at 0.5 to produce the final binary inundation mask.
        """
        if raster_data.ndim != 3 or raster_data.shape[0] != 6:
            raise ValueError(f"Expected raster of shape (6, H, W), got {raster_data.shape}")

        _, h, w = raster_data.shape
        stride = window_size - overlap

        # Handle scenes smaller than 512x512 with safe padding
        if h < window_size or w < window_size:
            pad_h = max(0, window_size - h)
            pad_w = max(0, window_size - w)
            padded = np.pad(raster_data, ((0, 0), (0, pad_h), (0, pad_w)), mode="reflect")
            pred_resp = model2_service.predict(padded[:, :window_size, :window_size], return_masks=True)
            prob_full = np.array(pred_resp.probability_mask)[:h, :w]
            binary_full = (prob_full >= model2_service.threshold).astype(np.uint8)
            return prob_full, binary_full

        # Determine sliding window coordinates
        row_starts = list(range(0, h - window_size + 1, stride))
        if row_starts[-1] + window_size < h:
            row_starts.append(h - window_size)

        col_starts = list(range(0, w - window_size + 1, stride))
        if col_starts[-1] + window_size < w:
            col_starts.append(w - window_size)

        prob_mosaic = np.zeros((h, w), dtype=np.float32)
        weight_mosaic = np.zeros((h, w), dtype=np.float32)

        # 2D window blending weights (bilinear pyramid weighting)
        y_w = np.sin(np.linspace(0, np.pi, window_size)).astype(np.float32)
        x_w = np.sin(np.linspace(0, np.pi, window_size)).astype(np.float32)
        blend_weights = np.outer(y_w, x_w)
        blend_weights = np.maximum(blend_weights, 0.05)

        for r in row_starts:
            for c in col_starts:
                window_slice = raster_data[:, r : r + window_size, c : c + window_size]
                # Preprocess: float32, / 10000.0, non-finite to 0.0, clip [0.0, 1.0]
                window_tensor = model2_service.preprocess_tensor(window_slice)
                device = model2_service._target_device
                model = model2_service._model

                if model is None:
                    model2_service.load()
                    model = model2_service._model

                with torch.no_grad():
                    logits = model(window_tensor.to(device))
                    probs = torch.sigmoid(logits).squeeze(0).squeeze(0).cpu().numpy()

                prob_mosaic[r : r + window_size, c : c + window_size] += probs * blend_weights
                weight_mosaic[r : r + window_size, c : c + window_size] += blend_weights

        # Normalize probability mosaic
        weight_mosaic = np.maximum(weight_mosaic, 1e-6)
        prob_mosaic = np.clip(prob_mosaic / weight_mosaic, 0.0, 1.0)
        binary_mask = (prob_mosaic >= model2_service.threshold).astype(np.uint8)

        return prob_mosaic, binary_mask

    @staticmethod
    def extract_open_ocean(
        binary_mask: np.ndarray,
        pixel_scale: float = 10.0,
        kernel_size: int = 7,
        min_ocean_area_km2: float = 15.0,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Morphologically separate vast open ocean / sea from inland river networks and water bodies.

        Rivers entering the sea (e.g. Cooum and Adyar in Chennai) are continuous with the open ocean
        at the coastline, forming a single contour. A morphological erosion decouples narrow channels (< 70m)
        from the massive open ocean seed (>= 15 km², spanning >= 40% of tile width/height, and touching the tile border).
        Dilation and boundary filtering then restores the ocean boundary back to the coast, leaving inland rivers
        and water bodies intact in land_water_mask.
        """
        h, w = binary_mask.shape
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
        eroded = cv2.erode(binary_mask.astype(np.uint8), kernel, iterations=1)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(eroded, connectivity=8)
        ocean_seed_mask = np.zeros_like(binary_mask, dtype=np.uint8)
        ocean_touch_borders = {"left": False, "right": False, "top": False, "bottom": False}

        for l in range(1, num_labels):
            area_px = stats[l, cv2.CC_STAT_AREA]
            area_km2 = (area_px * (pixel_scale ** 2)) / 1_000_000.0
            left = stats[l, cv2.CC_STAT_LEFT]
            top = stats[l, cv2.CC_STAT_TOP]
            width = stats[l, cv2.CC_STAT_WIDTH]
            height = stats[l, cv2.CC_STAT_HEIGHT]

            t_left = bool(left <= 1)
            t_right = bool(left + width >= w - 2)
            t_top = bool(top <= 1)
            t_bottom = bool(top + height >= h - 2)
            touches_border = t_left or t_right or t_top or t_bottom
            spans_tile = bool(width >= w * 0.40 or height >= h * 0.40)

            if area_km2 >= min_ocean_area_km2 and touches_border and spans_tile:
                ocean_seed_mask[labels == l] = 1
                if t_left:
                    ocean_touch_borders["left"] = True
                if t_right:
                    ocean_touch_borders["right"] = True
                if t_top:
                    ocean_touch_borders["top"] = True
                if t_bottom:
                    ocean_touch_borders["bottom"] = True

        if np.any(ocean_seed_mask):
            closed_seed = cv2.morphologyEx(
                ocean_seed_mask,
                cv2.MORPH_CLOSE,
                cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25)),
            )
            ocean_mask = (
                cv2.dilate(closed_seed, kernel, iterations=1) & binary_mask.astype(np.uint8)
            ).astype(np.uint8)

            # Prune stray wave noise / offshore speckles along the ocean-facing border
            ocean_rows, ocean_cols = np.where(ocean_mask > 0)
            min_ocean_col = int(np.min(ocean_cols)) if len(ocean_cols) > 0 else 0
            max_ocean_col = int(np.max(ocean_cols)) if len(ocean_cols) > 0 else w

            temp_land = (binary_mask.astype(np.uint8) & (~ocean_mask)).astype(np.uint8)
            num_c, lbls, stats_c, _ = cv2.connectedComponentsWithStats(temp_land, connectivity=8)
            for c in range(1, num_c):
                a_km2 = (stats_c[c, cv2.CC_STAT_AREA] * (pixel_scale ** 2)) / 1_000_000.0
                c_l = stats_c[c, cv2.CC_STAT_LEFT]
                if ocean_touch_borders["right"] and c_l > min_ocean_col + 20 and a_km2 < 0.05:
                    ocean_mask[lbls == c] = 1
                elif ocean_touch_borders["left"] and c_l + stats_c[c, cv2.CC_STAT_WIDTH] < max_ocean_col - 20 and a_km2 < 0.05:
                    ocean_mask[lbls == c] = 1

            land_mask = (binary_mask.astype(np.uint8) & (~ocean_mask)).astype(np.uint8)
        else:
            ocean_mask = np.zeros_like(binary_mask, dtype=np.uint8)
            land_mask = binary_mask.astype(np.uint8).copy()

        return ocean_mask, land_mask

    @staticmethod
    def classify_water_polygon(
        cnt: np.ndarray,
        h: int,
        w: int,
        area_sq_m: float,
        pixel_scale: float = 10.0,
    ) -> Tuple[bool, str]:
        """
        Classify vectorized water polygon into 'coastal_ocean', 'inland_water', or 'inundation'.
        """
        area_sq_km = area_sq_m / 1_000_000.0
        water_type = "inland_water" if area_sq_km >= 0.5 else "inundation"
        return False, water_type

    def polygonize_mask(
        self,
        binary_mask: np.ndarray,
        grid_metadata: Dict[str, Any],
        scene_id: str,
        acquisition_time: str,
        min_area_sq_m: float = 500.0,
    ) -> Tuple[InundationGeoJsonResponse, Dict[str, Any]]:
        """
        Vectorize binary flood mask into WGS84 GeoJSON polygons with outer and inner rings.
        Filters out noise polygons below min_area_sq_m.
        Classifies water polygons to separate open coastal/ocean waters from land-based inundation.
        Preserves raw water mask metrics internally while excluding open ocean from user-facing GeoJSON.
        """
        h, w = binary_mask.shape
        pixel_scale = float(grid_metadata.get("pixel_scale_m", 10.0))
        origin_x = float(grid_metadata["origin_x"])
        origin_y = float(grid_metadata["origin_y"])
        zone = int(grid_metadata["utm_zone"])
        north = bool(grid_metadata["utm_north"])

        # 1. Separate open ocean from land-based water bodies morphologically
        ocean_mask, land_mask = self.extract_open_ocean(binary_mask, pixel_scale=pixel_scale)

        def pixel_contour_to_wgs84(cnt: np.ndarray) -> List[List[float]]:
            ring: List[List[float]] = []
            for pt in cnt:
                px_c, px_r = float(pt[0][0]), float(pt[0][1])
                utm_e = origin_x + (px_c + 0.5) * pixel_scale
                utm_n = origin_y - (px_r + 0.5) * pixel_scale
                lat, lon = utm_to_latlon(utm_e, utm_n, zone=zone, north=north)
                ring.append([round(lon, 6), round(lat, 6)])
            if ring and ring[0] != ring[-1]:
                ring.append(ring[0])
            return ring

        def vectorize_binary_layer(layer_mask: np.ndarray, is_ocean: bool) -> List[InundationGeoJsonFeature]:
            contours, hierarchy = cv2.findContours(
                layer_mask.astype(np.uint8),
                cv2.RETR_CCOMP,
                cv2.CHAIN_APPROX_SIMPLE,
            )
            features: List[InundationGeoJsonFeature] = []
            if hierarchy is None or len(contours) == 0:
                return features

            hier = hierarchy[0]
            for idx, c in enumerate(contours):
                parent_idx = hier[idx][3]
                if parent_idx == -1:
                    raw_pixel_area = cv2.contourArea(c)
                    area_sq_m = raw_pixel_area * (pixel_scale ** 2)
                    if area_sq_m < min_area_sq_m:
                        continue

                    exterior_ring = pixel_contour_to_wgs84(c)
                    if len(exterior_ring) < 4:
                        continue

                    polygon_rings: List[List[List[float]]] = [exterior_ring]
                    child_idx = hier[idx][2]
                    while child_idx != -1:
                        child_c = contours[child_idx]
                        child_area_sq_m = cv2.contourArea(child_c) * (pixel_scale ** 2)
                        if child_area_sq_m >= min_area_sq_m:
                            hole_ring = pixel_contour_to_wgs84(child_c)
                            if len(hole_ring) >= 4:
                                polygon_rings.append(hole_ring)
                        child_idx = hier[child_idx][0]

                    perimeter_m = round(float(cv2.arcLength(c, True) * pixel_scale), 2)
                    water_type = "coastal_ocean" if is_ocean else ("inland_water" if (area_sq_m / 1_000_000.0) >= 0.5 else "inundation")

                    features.append(
                        InundationGeoJsonFeature(
                            type="Feature",
                            geometry=InundationPolygonGeometry(
                                type="Polygon",
                                coordinates=polygon_rings,
                            ),
                            properties=InundationPolygonProperties(
                                flooded_area_sq_m=round(area_sq_m, 2),
                                perimeter_m=perimeter_m,
                                scene_id=scene_id,
                                acquisition_time=acquisition_time,
                                source="Sentinel-2 L2A",
                                model_version="FloodUNet_v1",
                                water_type=water_type,
                                is_permanent_water=is_ocean,
                            ),
                        )
                    )
            return features

        user_facing_features = vectorize_binary_layer(land_mask, is_ocean=False)
        excluded_ocean_features = vectorize_binary_layer(ocean_mask, is_ocean=True) if np.any(ocean_mask) else []

        # Geodesic area calculations
        total_pixels = int(h * w)
        valid_area_sq_km = round(float((total_pixels * (pixel_scale ** 2)) / 1_000_000.0), 3)

        raw_flooded_pixels = int(np.sum(binary_mask == 1))
        raw_water_area_sq_km = round(float((raw_flooded_pixels * (pixel_scale ** 2)) / 1_000_000.0), 3)
        raw_flooded_pct = round(float((raw_flooded_pixels / total_pixels) * 100.0), 2) if total_pixels > 0 else 0.0

        land_flooded_pixels = int(np.sum(land_mask == 1))
        user_facing_area_sq_km = round(float((land_flooded_pixels * (pixel_scale ** 2)) / 1_000_000.0), 3)
        user_facing_pct = round(float((user_facing_area_sq_km / valid_area_sq_km) * 100.0), 2) if valid_area_sq_km > 0 else 0.0

        ocean_pixels = int(np.sum(ocean_mask == 1))
        excluded_water_area_sq_km = round(float((ocean_pixels * (pixel_scale ** 2)) / 1_000_000.0), 3)

        stats = {
            "valid_area_sq_km": valid_area_sq_km,
            "flooded_area_sq_km": user_facing_area_sq_km,
            "flooded_percentage": user_facing_pct,
            "polygon_count": len(user_facing_features),
            "water_pixel_count": land_flooded_pixels,
            "flooded_pixels": land_flooded_pixels,
            "total_pixels": total_pixels,
            "grid_resolution_m": pixel_scale,
            "dimensions": [int(h), int(w)],
            "raw_water_area_sq_km": raw_water_area_sq_km,
            "raw_water_percentage": raw_flooded_pct,
            "raw_polygon_count": len(user_facing_features) + len(excluded_ocean_features),
            "excluded_permanent_water_sq_km": excluded_water_area_sq_km,
            "permanent_water_polygon_count": len(excluded_ocean_features),
            "water_label": "Detected Surface Water (Permanent Coastal Ocean Excluded)" if len(excluded_ocean_features) > 0 else "Detected Surface Water",
        }

        geojson_resp = InundationGeoJsonResponse(
            type="FeatureCollection",
            features=user_facing_features,
        )

        return geojson_resp, stats
