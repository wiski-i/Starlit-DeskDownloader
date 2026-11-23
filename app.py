"""Native desktop interface and tray workflow."""

import json
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QSettings, Qt, QUrl
from PySide6.QtGui import (
    QActionGroup, QCloseEvent, QColor, QDesktopServices, QFont, QKeySequence, QPainter, QPaintEvent, QPen, QResizeEvent,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QKeySequenceEdit, QLabel, QLineEdit,
    QMenu, QMessageBox, QProgressBar, QPushButton, QSizePolicy, QSystemTrayIcon,
    QVBoxLayout, QWidget,
)

from browser_bridge import BrowserBridge, socket_name
from downloads import ROOT, DownloadJob, download_url
from media_profiles import FORMATS, DownloadProfile
from theme import (
    DIALOG_BACKGROUND, FOREGROUND, FRAME_BORDER, THEMES, WINDOW_BACKGROUND, app_icon, mark_pixmap, style_for,
)
from windows import (
    DEFAULT_SHORTCUT, AppInstance, BrowserCapture, Shortcut, downloads_folder, set_title_bar_colors, show_file,
)


COPY = json.loads((ROOT / "copy_tr.json").read_text(encoding="utf-8"))


def text(key: str) -> str:
    return COPY[key]


def label(value: str = "", *, size: int = 14, bold: bool = False, muted: bool = False) -> QLabel:
    widget = QLabel(value)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    font = widget.font()
    font.setPixelSize(size)
    font.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    widget.setFont(font)
    widget.setProperty("muted", muted)
    return widget


def button(key: str, callback=None, variant: str = "", height: int = 44) -> QPushButton:
    widget = QPushButton(text(key), objectName=variant)
    widget.setMinimumHeight(height)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if callback is not None:
        widget.clicked.connect(callback)
    return widget


def set_style_property(widget: QWidget, name: str, value) -> None:
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class ElidedLabel(QLabel):
    """Show long titles or paths with the full text accessible on hover."""

    def __init__(self, *, size: int = 13) -> None:
        super().__init__()
        self._full = ""
        self.setFont(label(size=size).font())
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setProperty("muted", True)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def set_full_text(self, value: str) -> None:
        self._full = value
        self.setToolTip(value)
        self.setAccessibleName(value)
        self._update_text()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_text()

    def _update_text(self) -> None:
        self.setText(self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideMiddle, self.width()))


class ChoiceBox(QComboBox):
    """Draw the drop-down chevron that the style sheet hides."""

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(FOREGROUND), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        x, y = self.width() - 20, self.height() / 2
        painter.drawPolyline([QPointF(x - 4, y - 2), QPointF(x, y + 2), QPointF(x + 4, y - 2)])
        painter.end()


class VideoWindow(QWidget):
    def __init__(self, application: QApplication, settings: QSettings, capture: BrowserCapture) -> None:
        super().__init__(objectName="window")
        self.application = application
        self.settings = settings
        self.capture = capture
        self.shortcut = Shortcut.parse(settings.value("shortcut", DEFAULT_SHORTCUT.portable, type=str)) or DEFAULT_SHORTCUT
        self.folder = Path(self.settings.value("downloadFolder") or downloads_folder())
        self.job: DownloadJob | None = None
        self.saved_file: Path | None = None
        self._item_title = ""
        self._canceling = False
        self._quitting = False

        self.setWindowTitle(text("name"))
        self.setWindowIcon(app_icon())
        self.setMinimumSize(575, 625)
        self.resize(752, 660)
        self._build()
        self._restore_download_profile()
        self._create_tray()
        self._apply_theme(self.settings.value("theme", "glass"))
        self._set_folder_label()
        self._set_status("idle")
        self.url.setFocus()
        set_title_bar_colors(int(self.winId()), WINDOW_BACKGROUND, FOREGROUND, FRAME_BORDER)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 20)
        layout.setSpacing(14)
        settings_menu = QMenu(self)
        settings_menu.addAction(text("shortcut"), self._choose_shortcut)
        self.theme_menu = settings_menu.addMenu(text("theme"))
        self.theme_group = QActionGroup(self)
        for theme in THEMES:
            action = self.theme_menu.addAction(text(theme))
            action.setCheckable(True)
            action.setData(theme)
            self.theme_group.addAction(action)
        self.theme_group.triggered.connect(lambda action: self._change_theme(action.data()))

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(mark_pixmap(31))
        toolbar.addWidget(logo)
        toolbar.addWidget(label(text("name"), size=18, bold=True))
        toolbar.addStretch()
        settings_button = button("settings", variant="quiet", height=38)
        settings_button.setMenu(settings_menu)
        toolbar.addWidget(settings_button)
        layout.addLayout(toolbar)
        layout.addWidget(self._hero())
        layout.addWidget(self._workbench())

        footer = QHBoxLayout()
        footer.setSpacing(12)
        path_column = QVBoxLayout()
        path_column.setSpacing(3)
        path_column.addWidget(label(text("folder"), size=12, bold=True, muted=True))
        self.folder_path = ElidedLabel()
        path_column.addWidget(self.folder_path)
        footer.addLayout(path_column, stretch=1)
        footer.addWidget(button("open_folder", self._open_folder, "quiet", height=40))
        self.change_button = button("change", self._choose_folder, height=40)
        footer.addWidget(self.change_button)
        layout.addLayout(footer)

    def _hero(self) -> QFrame:
        hero = QFrame(objectName="hero")
        layout = QHBoxLayout(hero)
        layout.setContentsMargins(24, 18, 24, 21)
        layout.setSpacing(16)
        intro = QVBoxLayout()
        intro.setSpacing(10)
        headline = label(text("headline"), size=31, bold=True)
        headline.setWordWrap(True)
        intro.addWidget(headline)
        self.shortcut_hint = label(text("shortcut_hint"), muted=True)
        self.shortcut_hint.setWordWrap(True)
        intro.addWidget(self.shortcut_hint)
        self.shortcut_keys = QWidget()
        self.keys_layout = QHBoxLayout(self.shortcut_keys)
        self.keys_layout.setContentsMargins(0, 0, 0, 0)
        self.keys_layout.setSpacing(5)
        self._render_shortcut()
        # Hiding the keycaps must not let the hint slide to the bottom of the hero.
        keys_policy = self.shortcut_keys.sizePolicy()
        keys_policy.setRetainSizeWhenHidden(True)
        self.shortcut_keys.setSizePolicy(keys_policy)
        intro.addWidget(self.shortcut_keys)
        layout.addLayout(intro, stretch=1)

        illustration = QLabel()
        illustration.setPixmap(mark_pixmap(116, detailed=True))
        layout.addWidget(illustration, alignment=Qt.AlignmentFlag.AlignVCenter)
        return hero

    def _workbench(self) -> QFrame:
        panel = QFrame(objectName="workbench")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(9)
        link_label = label(text("link"), size=13, bold=True)
        layout.addWidget(link_label)
        form = QHBoxLayout()
        form.setSpacing(8)
        self.url = QLineEdit(placeholderText=text("placeholder"), clearButtonEnabled=True)
        self.url.setAccessibleName(text("link"))
        self.url.setMinimumHeight(46)
        self.url.setMaxLength(16384)
        self.url.textEdited.connect(self._clear_feedback)
        self.url.returnPressed.connect(self._submit)
        link_label.setBuddy(self.url)
        self.paste_button = button("paste", self._paste)
        self.download_button = button("download", self._submit, "primary", height=46)
        self.download_button.setMinimumWidth(96)
        form.addWidget(self.url, stretch=1)
        form.addWidget(self.paste_button)
        form.addWidget(self.download_button)
        layout.addLayout(form)
        layout.addLayout(self._profile_row())

        self.feedback = label(size=13)
        self.feedback.setWordWrap(True)
        self.feedback.setProperty("tone", "error")
        self.feedback.hide()
        layout.addWidget(self.feedback)
        layout.addSpacing(4)
        rule = QFrame(objectName="rule")
        rule.setFixedHeight(1)
        layout.addWidget(rule)
        layout.addSpacing(2)

        status_row = QHBoxLayout()
        self.status = label(size=16, bold=True)
        self.percentage = label(size=14, bold=True)
        self.percentage.setProperty("tinted", True)
        status_row.addWidget(self.status)
        status_row.addStretch()
        status_row.addWidget(self.percentage)
        layout.addLayout(status_row)

        self.detail = ElidedLabel()
        self.detail.hide()
        layout.addWidget(self.detail)
        self.progress_bar = QProgressBar(textVisible=False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setAccessibleName(text("progress"))
        layout.addWidget(self.progress_bar)

        choice_row = QHBoxLayout()
        # Keeps Cancel / Show file at their natural width while the picker is hidden.
        choice_row.addStretch()
        self.choices = ChoiceBox()
        self.choices.setAccessibleName(text("selecting"))
        self.choices.setMinimumHeight(40)
        self.choices.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.choices.hide()
        choice_row.addWidget(self.choices, stretch=1)
        self.confirm_choice = button("download", self._select_video, "primary", height=40)
        self.confirm_choice.hide()
        choice_row.addWidget(self.confirm_choice)
        self.cancel_button = button("cancel", self._cancel, height=40)
        self.cancel_button.hide()
        choice_row.addWidget(self.cancel_button)
        self.show_file_button = button("show_file", self._show_file, height=40)
        self.show_file_button.hide()
        choice_row.addWidget(self.show_file_button)
        layout.addLayout(choice_row)
        self.setTabOrder(self.url, self.paste_button)
        self.setTabOrder(self.paste_button, self.download_button)
        return panel

    def _profile_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        self.format_box = ChoiceBox(objectName="formatBox")
        self.quality_box = ChoiceBox(objectName="qualityBox")
        for box, key in ((self.format_box, "format"), (self.quality_box, "quality")):
            column = QVBoxLayout()
            column.setSpacing(5)
            caption = label(text(key), size=13, bold=True)
            caption.setBuddy(box)
            box.setAccessibleName(text(key))
            box.setMinimumHeight(40)
            box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            column.addWidget(caption)
            column.addWidget(box)
            row.addLayout(column, stretch=1)

        model: QStandardItemModel = self.format_box.model()
        last_group = ""
        self.format_box.setMaxVisibleItems(12)
        for format_id, output in FORMATS.items():
            if output.group != last_group:
                self.format_box.addItem(text(f"format_group_{output.group}"))
                model.item(self.format_box.count() - 1).setEnabled(False)
                last_group = output.group
            self.format_box.addItem(output.label, format_id)
        return row

    def _restore_download_profile(self) -> None:
        saved = DownloadProfile.read_settings(self.settings)
        self.format_box.setCurrentIndex(self.format_box.findData(saved.format_id))
        self._refresh_qualities(persist=False)
        self.format_box.currentIndexChanged.connect(self._refresh_qualities)
        self.quality_box.currentIndexChanged.connect(self._save_download_profile)

    def _refresh_qualities(self, _index: int = -1, *, persist: bool = True) -> None:
        format_id = self.format_box.currentData()
        profile = DownloadProfile.read_settings(self.settings, format_id)
        self.quality_box.blockSignals(True)
        try:
            self.quality_box.clear()
            for quality in profile.output.qualities:
                self.quality_box.addItem(quality.label, quality.key)
            self.quality_box.setCurrentIndex(self.quality_box.findData(profile.quality))
        finally:
            self.quality_box.blockSignals(False)
        hint = f"quality_hint_{format_id}" if format_id in ("original", "flac", "wav") else (
            "quality_hint_video" if profile.output.video else "quality_hint_audio"
        )
        self.quality_box.setToolTip(text(hint))
        if persist:
            self._save_download_profile()

    def _download_profile(self) -> DownloadProfile:
        return DownloadProfile.from_setting(self.format_box.currentData(), self.quality_box.currentData())

    def _save_download_profile(self) -> None:
        self._download_profile().save_settings(self.settings)

    def _create_tray(self) -> None:
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip(text("name"))
        menu = QMenu(self)
        menu.addAction(text("show_window"), self.show_window)
        menu.addAction(text("open_folder"), self._open_folder)
        menu.addSeparator()
        menu.addAction(text("quit"), self._request_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.messageClicked.connect(self.show_window)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def _change_theme(self, theme: str) -> None:
        self._apply_theme(theme)
        self.settings.setValue("theme", theme)

    def _apply_theme(self, theme: str) -> None:
        self.setStyleSheet(style_for(theme))
        for action in self.theme_group.actions():
            action.setChecked(action.data() == theme)

    def _set_folder_label(self) -> None:
        self.folder_path.set_full_text(str(self.folder))

    def _choose_folder(self) -> None:
        selection = QFileDialog.getExistingDirectory(self, text("folder"), str(self.folder))
        if selection:
            self.folder = Path(selection)
            self.settings.setValue("downloadFolder", str(self.folder))
            self._set_folder_label()

    def _open_folder(self) -> None:
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            if QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.folder))):
                return
        except OSError:
            pass
        self.show_window()
        self._show_feedback("folder_error")

    def _show_file(self) -> None:
        if self.saved_file and not show_file(self.saved_file):
            self._show_feedback("folder_error")

    def set_shortcut_available(self, available: bool) -> None:
        self.shortcut_keys.setVisible(available)
        self.shortcut_hint.setText(text("shortcut_hint" if available else "shortcut_off"))

    def _render_shortcut(self) -> None:
        while self.keys_layout.count():
            old = self.keys_layout.takeAt(0).widget()
            if old:
                old.hide()
                old.deleteLater()
        for index, key in enumerate(self.shortcut.portable.split("+")):
            if index:
                self.keys_layout.addWidget(label("+", size=13, muted=True))
            keycap = label(key, size=13, bold=True)
            keycap.setObjectName("key")
            self.keys_layout.addWidget(keycap)
        self.keys_layout.addStretch()

    def _choose_shortcut(self) -> None:
        dialog = QDialog(self, objectName="shortcutDialog")
        dialog.setWindowTitle(text("shortcut"))
        dialog.setMinimumWidth(410)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.addWidget(label(text("shortcut"), size=18, bold=True))
        instruction = label(text("shortcut_instruction"), muted=True)
        instruction.setWordWrap(True)
        layout.addWidget(instruction)
        editor = QKeySequenceEdit(QKeySequence(self.shortcut.portable))
        editor.setMaximumSequenceLength(1)
        editor.setClearButtonEnabled(True)
        editor.setMinimumHeight(44)
        editor.setAccessibleName(text("shortcut"))
        layout.addWidget(editor)
        error = label(size=13)
        error.setProperty("tone", "error")
        error.setWordWrap(True)
        error.hide()
        layout.addWidget(error)

        def save() -> None:
            value = editor.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
            shortcut = Shortcut.parse(value)
            if shortcut is None:
                error.setText(text("shortcut_invalid"))
            elif not self.capture.set_shortcut(shortcut):
                error.setText(text("shortcut_conflict"))
            else:
                self.shortcut = shortcut
                self.settings.setValue("shortcut", shortcut.portable)
                self._render_shortcut()
                self.set_shortcut_available(True)
                dialog.accept()
                return
            error.show()

        actions = QHBoxLayout()
        actions.addWidget(button("reset_shortcut", lambda: editor.setKeySequence(QKeySequence(DEFAULT_SHORTCUT.portable)), "quiet"))
        actions.addStretch()
        actions.addWidget(button("close", dialog.reject))
        actions.addWidget(button("save", save, "primary"))
        layout.addLayout(actions)
        set_title_bar_colors(int(dialog.winId()), DIALOG_BACKGROUND, FOREGROUND, FRAME_BORDER)
        dialog.exec()

    def handle_capture(self, address: str) -> None:
        if self.job:
            self.show_window()
            return
        if not address:
            self.show_window()
            self._show_feedback("capture_missing")
            self.url.setFocus()
            return
        self.submit_browser_url(address)

    def submit_browser_url(self, address: str, *, profile: DownloadProfile | None = None) -> str:
        if self.job or self._quitting:
            return "busy"
        address = download_url(address)
        if not address:
            return "invalid_url"
        self.url.setText(address)
        if not self.tray.isVisible():
            self.show_window()
        self._start_download(address, profile if profile is not None else self._download_profile())
        self._notify("background")
        return "accepted"

    def show_window(self) -> None:
        if self.isMinimized():
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.show()
        self.raise_()
        self.activateWindow()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window()

    def _notify(self, key: str) -> None:
        if not self.isActiveWindow() and self.tray.isVisible():
            self.tray.showMessage(text("name"), text(key), self.windowIcon(), 3000)

    def _paste(self) -> None:
        address = download_url(self.application.clipboard().text())
        if not address:
            self._show_feedback("paste_missing")
            return
        self._clear_feedback()
        self.url.setText(address)
        self.url.setFocus()

    def _show_feedback(self, key: str) -> None:
        self.feedback.setText(text(key))
        self.feedback.show()
        set_style_property(self.url, "invalid", key in ("invalid_url", "paste_missing"))

    def _clear_feedback(self) -> None:
        self.feedback.hide()
        set_style_property(self.url, "invalid", False)

    def _submit(self) -> None:
        if self.job:
            return
        address = download_url(self.url.text())
        if not address:
            self._show_feedback("invalid_url")
            self.url.setFocus()
            return
        self._start_download(address, self._download_profile())

    def _start_download(self, address: str, profile: DownloadProfile) -> None:
        self._clear_feedback()
        self.saved_file = None
        self._item_title = ""
        self._canceling = False
        self.cancel_button.setEnabled(True)
        self.cancel_button.show()
        self.show_file_button.hide()
        set_style_property(self.progress_bar, "tone", "")
        self._set_input_enabled(False)
        self._set_status("detecting", percent=-1)

        job = self.job = DownloadJob(address, self.folder, self, profile=profile)
        job.title_changed.connect(self._set_title)
        job.choices_found.connect(self._offer_choices)
        job.progress_changed.connect(self._set_progress)
        job.processing.connect(self._processing)
        job.saved.connect(self._saved)
        job.failed.connect(self._failed)
        job.cancelled.connect(self._cancelled)
        job.finished.connect(self._release_job)
        job.start()

    def _set_input_enabled(self, enabled: bool) -> None:
        for control in (self.url, self.paste_button, self.download_button, self.change_button,
                        self.format_box, self.quality_box):
            control.setEnabled(enabled)

    def _set_status(self, key: str, detail: str = "", percent: int | None = None, tone: str = "") -> None:
        self.status.setText(text(key))
        set_style_property(self.status, "tone", tone)
        self.detail.set_full_text(detail)
        self.detail.setVisible(bool(detail))
        self.progress_bar.setRange(0, 0 if percent == -1 else 100)
        if percent != -1:
            self.progress_bar.setValue(percent or 0)
        self.percentage.setText(f"%{percent}" if percent is not None and percent >= 0 else "")

    def _set_title(self, title: str) -> None:
        self._item_title = title
        if title and not self._canceling:
            self.detail.set_full_text(title)
            self.detail.show()

    def _offer_choices(self, titles: list[str]) -> None:
        if self._canceling:
            return
        self._set_status("selecting", text("selecting_hint"))
        self.choices.clear()
        for index, title in enumerate(titles, 1):
            self.choices.addItem(title or text("candidate").format(number=index))
        self.choices.show()
        self.confirm_choice.show()
        self.show_window()
        self.choices.setFocus()

    def _select_video(self) -> None:
        if self.job:
            self.job.select(self.choices.currentIndex())
            self.choices.hide()
            self.confirm_choice.hide()
            self._set_status("detecting", percent=-1)

    def _set_progress(self, percent: int, speed: float, eta: int) -> None:
        if self._canceling:
            return
        detail = [self._item_title]
        if speed:
            unit, divisor = ("MB/s", 1024**2) if speed >= 1024**2 else ("KB/s", 1024)
            detail.append(f"{speed / divisor:.1f} {unit}".replace(".", ","))
        if eta >= 0:
            minutes, seconds = divmod(eta, 60)
            detail.append(text("remaining").format(time=f"{minutes}:{seconds:02d}"))
        self._set_status("downloading", "  ·  ".join(filter(None, detail)), percent)

    def _processing(self) -> None:
        if not self._canceling:
            self._set_status("processing", self._item_title, percent=-1)

    def _saved(self, path: str) -> None:
        self.saved_file = Path(path)
        self._set_status("done", self.saved_file.name, percent=100, tone="success")
        set_style_property(self.progress_bar, "tone", "success")
        self.show_file_button.show()
        self._notify("done")

    def _failed(self, key: str) -> None:
        self._set_status("failed", tone="error")
        self._show_feedback(key)
        self._notify("failed")

    def _cancel(self) -> None:
        if self.job and not self._canceling:
            self._canceling = True
            self.job.cancel()
            self.cancel_button.setEnabled(False)
            self.choices.hide()
            self.confirm_choice.hide()
            self._set_status("canceling", percent=-1)

    def _cancelled(self) -> None:
        self._set_status("canceled")

    def _release_job(self) -> None:
        if self.job:
            self.job.deleteLater()
            self.job = None
        self.choices.hide()
        self.confirm_choice.hide()
        self.cancel_button.hide()
        self._set_input_enabled(True)
        if self._quitting:
            self.application.quit()

    def _request_quit(self) -> None:
        if not self.job:
            self.application.quit()
            return
        confirmation = QMessageBox(self)
        confirmation.setWindowTitle(text("name"))
        confirmation.setText(text("confirm_exit"))
        confirmation.addButton(text("keep_open"), QMessageBox.ButtonRole.RejectRole)
        quit_button = confirmation.addButton(text("exit_now"), QMessageBox.ButtonRole.DestructiveRole)
        set_title_bar_colors(int(confirmation.winId()), DIALOG_BACKGROUND, FOREGROUND, FRAME_BORDER)
        confirmation.exec()
        if confirmation.clickedButton() == quit_button:
            self._quitting = True
            if self.job:
                self._cancel()
            else:
                self.application.quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        event.ignore()
        if self.tray.isVisible():
            self.hide()
        else:
            self._request_quit()


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName(text("name"))
    application.setFont(QFont("Segoe UI", 10))
    application.setQuitOnLastWindowClosed(False)
    instance = AppInstance(application)
    if instance.is_secondary:
        return 0
    settings = QSettings("HizliIndir", "HizliIndir")
    capture = BrowserCapture(ROOT / "browser_address.ps1", application)
    window = VideoWindow(application, settings, capture)
    bridge = BrowserBridge(window.submit_browser_url, application)
    bridge.listen(socket_name())
    capture.captured.connect(window.handle_capture)
    window.set_shortcut_available(capture.start(window.shortcut))
    instance.reopen_requested.connect(window.show_window)
    application.aboutToQuit.connect(capture.stop)
    application.aboutToQuit.connect(instance.close)
    application.aboutToQuit.connect(bridge.close)
    window.show()
    return application.exec()


if __name__ == "__main__":
    sys.exit(main())
