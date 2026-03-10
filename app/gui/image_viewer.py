import numpy as np
import cv2

from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem
from PySide6.QtGui import QPixmap, QImage, QPainter, QWheelEvent, QPen, QColor
from PySide6.QtCore import Qt, QRectF, QPointF


def _to_uint8(arr: np.ndarray, max_px: int = 2000) -> np.ndarray:
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, axis=-1)
    h, w = arr.shape[:2]
    # Сначала ресайз на float32 (маленький буфер), потом конвертация.
    if max(h, w) > max_px:
        scale = max_px / max(h, w)
        arr = cv2.resize(arr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    if arr.dtype != np.uint8:
        arr = (np.clip(arr, 0, 1) * 255).astype(np.uint8)
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

        self._pixmap_w: int | None = None
        self._pixmap_h: int | None = None

        self._base_arr_u8: np.ndarray | None = None
        self._brightness = 0
        self._contrast   = 1.0
        self._sharpness  = 0.0

    # Public API

    def set_image(self, arr: np.ndarray, reset_zoom: bool = False):
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
        # Enhancement (пропускаем float-конвертацию на дефолтах)
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
        new_h, new_w = arr.shape[:2]
        pixmap = _arr_to_pixmap(arr)

        size_changed = (new_w != self._pixmap_w or new_h != self._pixmap_h)

        saved_norm = None
        if self._user_zoomed and not reset_zoom and size_changed and self._pixmap_w:
            vtl = self.mapToScene(self.viewport().rect().topLeft())
            vbr = self.mapToScene(self.viewport().rect().bottomRight())
            saved_norm = (
                (vtl.x() / self._pixmap_w, vtl.y() / self._pixmap_h),
                (vbr.x() / self._pixmap_w, vbr.y() / self._pixmap_h),
            )

        if self._pixmap_item is None:
            self._pixmap_item = self._scene.addPixmap(pixmap)
        else:
            self._pixmap_item.setPixmap(pixmap)

        self._pixmap_w = new_w
        self._pixmap_h = new_h

        r = self._pixmap_item.boundingRect()
        pad = max(r.width(), r.height())
        self._scene.setSceneRect(r.adjusted(-pad, -pad, pad, pad))

        if reset_zoom:
            # Явный сброс (новые результаты)
            self._user_zoomed = False
            self.resetTransform()
            self.fit()
            self._fit_transform = self.transform()

        elif not self._user_zoomed:
            self.resetTransform()
            self.fit()
            self._fit_transform = self.transform()

        elif saved_norm:
            (ntl, nbr) = saved_norm
            new_tl = QPointF(ntl[0] * new_w, ntl[1] * new_h)
            new_br = QPointF(nbr[0] * new_w, nbr[1] * new_h)

            self.fitInView(QRectF(new_tl, new_br), Qt.AspectRatioMode.KeepAspectRatio)
            restored = self.transform()
            new_center = QPointF(
                (ntl[0] + nbr[0]) / 2 * new_w,
                (ntl[1] + nbr[1]) / 2 * new_h,
            )

            self.resetTransform()
            self.fit()
            self._fit_transform = self.transform()
            self.setTransform(restored)
            self.centerOn(new_center)  # pan тоже восстанавливаем через centerOn
            self._user_zoomed = True

        else:
            scene_center = self.mapToScene(self.viewport().rect().center())
            current = self.transform()
            self.resetTransform()
            self.fit()
            self._fit_transform = self.transform()
            self.setTransform(current)
            self.centerOn(scene_center)

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
