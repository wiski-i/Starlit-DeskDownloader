"""Draw the native window's burgundy glass surfaces and download mark."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPen, QPixmap


THEMES = ("glass", "quiet", "technical")
WINDOW_BACKGROUND = "#170f17"
DIALOG_BACKGROUND = "#241822"
FOREGROUND = "#fcf2f5"
FRAME_BORDER = "#503345"

STYLE = """
QWidget#window { background: %(window)s; color: %(foreground)s; }
QDialog#shortcutDialog, QMessageBox { background: %(dialog)s; }
QLabel { color: %(foreground)s; background: transparent; }
QLabel[muted="true"] { color: #cab4be; }
QLabel[tinted="true"] { color: #ffc4d6; }
QLabel[tone="success"] { color: #b7ead8; }
QLabel[tone="error"] { color: #ffb6c4; }
QLabel#key {
    background: #2b1924; color: #fff2f7; border: 1px solid #906075;
    border-bottom: 2px solid #906075; border-radius: 7px; padding: 4px 9px;
}
QFrame#hero {
    background: qlineargradient(x1:0, y1:1, x2:1, y2:0,
        stop:0 #2d1825, stop:0.53 #451d31, stop:1 #711b36);
    border: 1px solid #945473; border-radius: 24px;
}
QFrame#workbench {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #241822, stop:1 #1f151d);
    border: 1px solid %(border)s; border-radius: 20px;
}
QFrame#rule { background: %(border)s; border: 0; }
QLineEdit, QComboBox {
    color: #fff3f8; background: #191018; border: 1px solid #705164;
    border-radius: 10px; padding: 0 12px; selection-background-color: #9a3e5e;
}
QLineEdit[invalid="true"] { border: 1px solid #f495aa; }
QLineEdit:disabled { color: #cab4be; }
QKeySequenceEdit QLineEdit { min-height: 38px; padding: 0 10px; }
QKeySequenceEdit QLineEdit:focus { border: 2px solid #ffb3ce; }
QComboBox::drop-down { width: 28px; border: 0; }
QComboBox QAbstractItemView {
    color: #fff3f8; background: #2b1924; border: 1px solid #906075;
    selection-background-color: #813149; selection-color: white;
}
QPushButton {
    background: #382331; color: #fff0f6; border: 1px solid #6f4b5f;
    border-radius: 10px; padding: 0 14px; font-weight: 600;
}
QPushButton:hover { background: #4c2c3e; border-color: #a36b85; }
QPushButton:pressed { background: #291a25; }
QPushButton#primary {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #a83d60, stop:1 #81314f);
    border-color: #d17b98; color: #fffaff;
}
QPushButton#primary:hover { background: #ac4065; border-color: #eda8be; }
QPushButton#primary:pressed { background: #80304b; }
QPushButton#quiet { background: transparent; border-color: transparent; color: #f9d9e5; }
QPushButton#quiet:hover { background: #382331; border-color: #6f4b5f; }
QPushButton:disabled, QPushButton#primary:disabled, QPushButton#quiet:disabled {
    background: #392a34; color: #bdacb7; border-color: #4c3945;
}
QPushButton:focus, QPushButton#quiet:focus, QPushButton#primary:focus,
QLineEdit:focus, QComboBox:focus { border: 2px solid #ffb3ce; }
QProgressBar { background: #342331; border: 0; border-radius: 4px; }
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #af4370, stop:1 #ffabc5);
    border-radius: 4px;
}
QProgressBar[tone="success"]::chunk { background: #87d7ba; }
QMenu { color: #fff3f8; background: #2a1a26; border: 1px solid #79556b; padding: 5px; }
QMenu::item { padding: 8px 24px 8px 19px; }
QMenu::item:selected { background: #733652; }
QToolTip { color: #fff3f8; background: #2d1a27; border: 1px solid #79556b; }
""" % {"window": WINDOW_BACKGROUND, "dialog": DIALOG_BACKGROUND, "foreground": FOREGROUND, "border": FRAME_BORDER}

THEME_OVERRIDES = {
    "glass": "",
    "quiet": """
        QFrame#hero { background: #30202b; border-color: #704d62; }
        QFrame#workbench { background: #211720; }
        QPushButton#primary { background: #843451; }
    """,
    "technical": """
        QFrame#hero { background: #241824; border-color: #87586f; border-radius: 14px; }
        QFrame#workbench { background: #211721; border-radius: 12px; }
        QLabel#key { background: #20131d; border-color: #a0788a; }
    """,
}


def style_for(theme: str) -> str:
    return STYLE + THEME_OVERRIDES.get(theme, "")


def _line(painter: QPainter, x1: float, y1: float, x2: float, y2: float) -> None:
    painter.drawLine(x1, y1, x2, y2)


def mark_pixmap(size: int, detailed: bool = False) -> QPixmap:
    """Render the app icon and its larger illustration at the requested pixel size."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 128, size / 128)
    surface = QLinearGradient(16, 12, 112, 117)
    surface.setColorAt(0, QColor("#b65376"))
    surface.setColorAt(0.52, QColor("#711b36"))
    surface.setColorAt(1, QColor("#401528"))
    painter.setBrush(surface)
    painter.setPen(QPen(QColor("#d989a8"), 1.5))
    painter.drawRoundedRect(QRectF(4, 4, 120, 120), 29, 29)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if detailed:
        painter.setPen(QPen(QColor("#b76183"), 1))
        painter.drawRoundedRect(QRectF(10, 10, 108, 108), 24, 24)
        for offset in (19, 25, 31):
            _line(painter, 19, offset + 64, 26, offset + 64)
            _line(painter, 102, offset - 1, 109, offset - 1)
    painter.setPen(QPen(QColor("#e5a2ba"), 3.25, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawRoundedRect(QRectF(31, 38, 66, 49), 10, 10)
    painter.setPen(QPen(QColor("#ffeff5"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    _line(painter, 64, 27, 64, 67)
    _line(painter, 51, 55, 64, 68)
    _line(painter, 77, 55, 64, 68)
    painter.setPen(QPen(QColor("#e5a2ba"), 3.25, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    _line(painter, 52, 98, 76, 98)
    painter.end()
    return pixmap


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(mark_pixmap(size))
    return icon
