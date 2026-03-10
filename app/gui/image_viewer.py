import numpy as np
import cv2

from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem
from PySide6.QtGui import QPixmap, QImage, QPainter, QWheelEvent, QPen, QColor
from PySide6.QtCore import Qt, QRectF


def _to_uint8(arr: np.ndarray, max_px: int = 2000) -> np.ndarray:
    if arr.dtype != np.uint8:
        arr = (np.clip(arr, 0, 1) * 255).astype(np.uint8)
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, axis=-1)
    h, w = arr.shape[:2]
    if max(h, w) > max_px:
        scale = max_px / max(h, w)
        arr = cv2.resize(arr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return np.ascontiguousarray(arr)


def _arr_to_pixmap(arr_u8: np.ndarray) -> QPixmap:
    h, w = arr_u8.shape[:2]
    qimg = QImage(arr_u8.data, w, h, w * 3, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg)


class ImageViewer(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing, True)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setBackgroundBrush(Qt.GlobalColor.darkGray)

        self._pixmap_item = None
        self._highlight_item: QGraphicsRectItem | None = None
        self._fit_transform = None
        self._user_zoomed = False

        # Enhancement params
        self._base_arr_u8: np.ndarray | None = None
        self._orig_shape: tuple[int, int] | None = None
        self._brightness = 0      # -100 .. 100
        self._contrast   = 1.0    # 0.5 .. 3.0
        self._sharpness  = 0.0    # 0.0 .. 3.0

    # Public API

    def set_image(self, arr: np.ndarray, reset_zoom: bool = False):
        """float32 [0..1] или uint8, (H,W) или (H,W,3). Зум не сбрасывается по умолчанию."""
        self._orig_shape = arr.shape[:2]
        self._base_arr_u8 = _to_uint8(arr)
        self.clear_highlight()
        self._apply_and_show(reset_zoom=reset_zoom)

    def set_image_u8(self, arr_u8: np.ndarray, reset_zoom: bool = False):
        """Принимает готовый uint8 массив — без конвертации и ресайза."""
        self._base_arr_u8 = arr_u8
        self.clear_highlight()
        self._apply_and_show(reset_zoom=reset_zoom)

    def set_enhancement(self, brightness: int = 0, contrast: float = 1.0, sharpness: float = 0.0):
        self._brightness = brightness
        self._contrast   = contrast
        self._sharpness  = sharpness
        if self._base_arr_u8 is not None:
            self._apply_and_show(reset_zoom=False)

    def highlight_object(self, contour, orig_shape: tuple[int, int]):
        self.clear_highlight()
        if contour is None or self._base_arr_u8 is None:
            return

        orig_h, orig_w = orig_shape
        disp_h, disp_w = self._base_arr_u8.shape[:2]
        sx = disp_w / orig_w
        sy = disp_h / orig_h

        x, y, w, h = cv2.boundingRect(contour)
        rx, ry = x * sx, y * sy
        rw, rh = w * sx, h * sy

        pen = QPen(QColor(255, 220, 0), 2)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        self._highlight_item = self._scene.addRect(rx, ry, rw, rh, pen)

        pad_x = max(rw * 0.4, 20)
        pad_y = max(rh * 0.4, 20)
        fit_rect = QRectF(rx - pad_x, ry - pad_y, rw + pad_x * 2, rh + pad_y * 2)
        self.fitInView(fit_rect, Qt.AspectRatioMode.KeepAspectRatio)
        self._user_zoomed = True

    def clear_highlight(self):
        if self._highlight_item:
            self._scene.removeItem(self._highlight_item)
            self._highlight_item = None

    def fit(self):
        if self._pixmap_item:
            self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def reset_zoom(self):
        self._user_zoomed = False
        self.resetTransform()
        self.fit()
        self._fit_transform = self.transform()

    # Internal

    def _apply_and_show(self, reset_zoom: bool):
        # Пропускаем float-конвертацию если enhancement на дефолтах
        if self._brightness == 0 and self._contrast == 1.0 and self._sharpness == 0.0:
            arr = self._base_arr_u8
        else:
            arr = self._base_arr_u8.astype(np.float32)

            if self._brightness != 0:
                arr += self._brightness

            if self._contrast != 1.0:
                arr = (arr - 128.0) * self._contrast + 128.0

            arr = np.clip(arr, 0, 255).astype(np.uint8)

            if self._sharpness > 0.0:
                blurred = cv2.GaussianBlur(arr, (0, 0), 2.0)
                arr = cv2.addWeighted(arr, 1.0 + self._sharpness, blurred, -self._sharpness, 0)
                arr = np.clip(arr, 0, 255).astype(np.uint8)

        arr = np.ascontiguousarray(arr)
        pixmap = _arr_to_pixmap(arr)

        if self._pixmap_item is None:
            self._pixmap_item = self._scene.addPixmap(pixmap)
        else:
            self._pixmap_item.setPixmap(pixmap)

        r = self._pixmap_item.boundingRect()
        pad = max(r.width(), r.height())
        self._scene.setSceneRect(r.adjusted(-pad, -pad, pad, pad))

        if reset_zoom:
            self._user_zoomed = False
            self.resetTransform()
            self.fit()
            self._fit_transform = self.transform()

    # Qt events

    def wheelEvent(self, event: QWheelEvent):
        factor = 1.25 if event.angleDelta().y() > 0 else 1 / 1.25
        new_scale = self.transform().m11() * factor
        if self._fit_transform and new_scale < self._fit_transform.m11():
            self.resetTransform()
            self.fit()
            self._user_zoomed = False
            return
        self._user_zoomed = True
        self.scale(factor, factor)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._pixmap_item and not self._user_zoomed:
            self.fit()
            self._fit_transform = self.transform()
