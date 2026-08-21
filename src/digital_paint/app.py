from __future__ import annotations

from pathlib import Path
import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox


def _write_startup_log(text: str) -> Path:
    root = Path.home() / ".digital_paint_by_numbers"
    root.mkdir(parents=True, exist_ok=True)
    path = root / "startup_error.log"
    path.write_text(text, encoding="utf-8")
    return path


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("数字油画生产软件")
    try:
        from digital_paint.ui.main_window import MainWindow

        window = MainWindow()
        window.show()
        return app.exec()
    except Exception:
        details = traceback.format_exc()
        try:
            log_path = _write_startup_log(details)
            message = f"数字油画软件启动失败。\n\n错误日志：\n{log_path}\n\n{details[-3000:]}"
        except Exception:
            message = f"数字油画软件启动失败。\n\n{details[-3000:]}"
        QMessageBox.critical(None, "数字油画 V100 RC1 启动错误", message)
        print(details, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
