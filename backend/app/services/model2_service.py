"""Model 2 (U-Net Flood Inundation Segmentation) real inference service."""

from datetime import datetime, timezone
import logging
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional
import numpy as np
import torch

from backend.app.core.config import get_settings
from backend.app.core.errors import ModelNotLoadedError
from backend.app.models.flood_unet import FloodUNet
from backend.app.schemas.common import GeoBoundingBox
from backend.app.schemas.prediction import InundationPrediction, InundationPredictionResponse
from backend.app.schemas.satellite import Sentinel2Bands
from backend.app.services.base import BaseService

logger = logging.getLogger("rainfall_backend.services.Model2Service")

EXPECTED_BANDS: List[str] = ["B2", "B3", "B4", "B8", "B11", "B12"]


class Model2Service(BaseService):
    """
    Real FloodUNet 6-Band Sentinel-2 Flood Inundation Segmentation Service.
    - Loads best_model.pth checkpoint
    - Enforces input channels [B2, B3, B4, B8, B11, B12]
    - Applies training preprocessing:
        1. float32 conversion
        2. divide by 10000.0 (reflectance scale)
        3. replace non-finite with 0
        4. clip to [0, 1]
    - Runs in eval() mode with torch.no_grad()
    - Configurable hardware device (CUDA, MPS, CPU)
    - Thread-safe singleton model caching
    """

    _instance: Optional["Model2Service"] = None
    _lock: threading.Lock = threading.Lock()
    _model: Optional[FloodUNet] = None
    _device: Optional[torch.device] = None
    _loaded_path: Optional[Path] = None

    def __init__(self, model_path: Optional[str] = None):
        super().__init__(
            name="Model2Service",
            description="U-Net 6-band Sentinel-2 flood inundation pixel segmentation",
        )
        self.settings = get_settings()
        self.model_path = Path(model_path or self.settings.MODEL2_PATH)
        self.threshold = self.settings.MODEL2_THRESHOLD
        self._target_device = self._resolve_device(self.settings.MODEL2_DEVICE)

    @classmethod
    def get_instance(cls, model_path: Optional[str] = None) -> "Model2Service":
        """Get or initialize singleton service instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(model_path=model_path)
            return cls._instance

    def _resolve_device(self, device_config: str) -> torch.device:
        """Determine appropriate torch execution device."""
        dev = device_config.lower().strip()
        if dev == "cuda" and torch.cuda.is_available():
            return torch.device("cuda")
        elif dev == "mps" and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        elif dev == "cpu":
            return torch.device("cpu")
        elif dev == "mps" and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        elif dev == "auto":
            # Per prompt requirement: Use CUDA when configured/available, otherwise CPU
            if torch.cuda.is_available():
                return torch.device("cuda")
            return torch.device("cpu")
        return torch.device("cpu")

    @property
    def is_loaded(self) -> bool:
        """Check if PyTorch model is actively loaded in memory."""
        return self.__class__._model is not None

    @property
    def is_connected(self) -> bool:
        return self.is_loaded

    def check_connection(self) -> bool:
        return self.is_loaded

    def resolve_model_file(self) -> Path:
        """Resolve model checkpoint file on disk or raise FileNotFoundError."""
        resolved = self.model_path if self.model_path.is_absolute() else (Path.cwd() / self.model_path)
        if resolved.is_file():
            return resolved

        repo_root = Path(__file__).resolve().parents[3]
        for candidate in [
            repo_root / "models" / self.model_path.name,
            repo_root / self.model_path.name,
            repo_root / self.model_path,
        ]:
            if candidate.is_file():
                return candidate

        raise FileNotFoundError(f"Model 2 file not found at '{self.model_path}' or in '{repo_root / 'models'}'")

    def has_model_artifact(self) -> bool:
        """Check if model checkpoint exists on disk."""
        try:
            self.resolve_model_file()
            return True
        except FileNotFoundError:
            return False

    def load(self, force_reload: bool = False) -> None:
        """
        Load FloodUNet weights from checkpoint.
        Thread-safe; avoids reloading if already loaded unless force_reload=True.
        """
        with self.__class__._lock:
            if self.__class__._model is not None and not force_reload:
                return

            try:
                resolved_file = self.resolve_model_file()
                device = self._target_device
                logger.info("Loading Model 2 (FloodUNet) from: %s on device: %s", resolved_file, device)

                model = FloodUNet(in_channels=6, base_channels=32, out_channels=1)
                checkpoint = torch.load(str(resolved_file), map_location="cpu", weights_only=False)
                state_dict = checkpoint.get("model_state_dict", checkpoint)
                model.load_state_dict(state_dict)
                model.to(device)
                model.eval()

                self.__class__._model = model
                self.__class__._device = device
                self.__class__._loaded_path = resolved_file
                self._is_connected = True
                logger.info("Model 2 (FloodUNet) loaded successfully on %s (7,763,905 params)", device)
            except Exception as exc:
                self.__class__._model = None
                self.__class__._device = None
                self._is_connected = False
                self._last_error = str(exc)
                logger.error("Failed to load Model 2: %s", exc)
                raise

    def get_health_detail(self) -> Dict[str, Any]:
        """Return detailed health state for /api/v1/models/health."""
        return {
            "loaded": self.is_loaded,
            "path_configured": self.has_model_artifact(),
            "model_type": "pytorch_unet",
            "checkpoint_path": str(self.__class__._loaded_path or self.model_path),
            "threshold": self.threshold,
            "device": str(self.__class__._device) if self.__class__._device else "none",
            "details": {
                "input_bands": EXPECTED_BANDS,
                "input_channels": 6,
                "last_error": self._last_error,
            },
        }

    def preprocess_tensor(self, raw_array: np.ndarray) -> torch.Tensor:
        """
        Apply Sen1Floods11 training preprocessing pipeline:
        1. convert to float32
        2. divide by 10000.0 (reflectance scale)
        3. replace non-finite values with 0
        4. clip to [0, 1]
        5. check channel count and shape
        """
        # Expected shape: (6, H, W) or (1, 6, H, W)
        if raw_array.ndim == 2:
            raise ValueError("Expected 3D (6, H, W) or 4D (B, 6, H, W) array, got 2D")
        elif raw_array.ndim == 3:
            if raw_array.shape[0] != 6:
                raise ValueError(
                    f"Expected 6 input bands [B2, B3, B4, B8, B11, B12] as first dimension, got {raw_array.shape[0]}"
                )
            arr = np.expand_dims(raw_array, axis=0)  # (1, 6, H, W)
        elif raw_array.ndim == 4:
            if raw_array.shape[1] != 6:
                raise ValueError(f"Expected 6 channels as second dimension, got {raw_array.shape[1]}")
            arr = raw_array
        else:
            raise ValueError(f"Unsupported array dimension: {raw_array.ndim}")

        # Float32 conversion
        arr = arr.astype(np.float32)

        # Non-finite check & replacement
        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)

        # Reflectance scale division
        arr = arr / 10000.0

        # Clipping to [0, 1]
        arr = np.clip(arr, 0.0, 1.0)

        return torch.from_numpy(arr)

    def predict(
        self,
        raster_data: np.ndarray,
        bounding_box: Optional[GeoBoundingBox] = None,
        return_masks: bool = True,
    ) -> InundationPredictionResponse:
        """
        Execute real FloodUNet segmentation inference.
        - raster_data: (6, H, W) numpy array in band order [B2, B3, B4, B8, B11, B12].
        """
        if not self.is_loaded:
            try:
                self.load()
            except Exception as err:
                raise ModelNotLoadedError(
                    model_name="flood_unet_sentinel2_6band",
                    path=str(self.model_path),
                    details={"error": str(err)},
                )

        model = self.__class__._model
        device = self.__class__._device
        if model is None or device is None:
            raise ModelNotLoadedError(
                model_name="flood_unet_sentinel2_6band",
                path=str(self.model_path),
            )

        tensor = self.preprocess_tensor(raster_data).to(device)
        _, _, h, w = tensor.shape

        with torch.no_grad():
            logits = model(tensor)  # (1, 1, H, W)
            probs = torch.sigmoid(logits).squeeze(0).squeeze(0).cpu().numpy()  # (H, W)

        binary = (probs >= self.threshold).astype(np.uint8)

        total_pixels = int(h * w)
        water_pixels = int(np.sum(binary == 1))
        flood_pct = round(float((water_pixels / total_pixels) * 100.0), 2) if total_pixels > 0 else 0.0

        return InundationPredictionResponse(
            model="flood_unet_sentinel2_6band",
            dimensions=[int(h), int(w)],
            water_pixel_count=water_pixels,
            total_valid_pixels=total_pixels,
            flooded_area_percentage=flood_pct,
            threshold=self.threshold,
            device=str(device),
            probability_mask=probs.round(4).tolist() if return_masks else None,
            binary_mask=binary.tolist() if return_masks else None,
            metadata={
                "input_bands": EXPECTED_BANDS,
                "input_channels": 6,
                "reflectance_scale": 10000.0,
                "bounding_box": bounding_box.model_dump() if bounding_box else None,
            },
        )

    def predict_inundation(self, bands: Sentinel2Bands) -> InundationPrediction:
        """Domain adapter method fulfilling original service interface."""
        raise NotImplementedError(
            "Band raster path downloading belongs to data ingestion pipeline. Use predict() with 6-band tensor."
        )
