import sys
import os
import asyncio
import json
import websockets
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QFrame, QGraphicsDropShadowEffect,
                             QInputDialog, QMessageBox, QScrollArea)
from PyQt6.QtGui import QColor, QFont, QIcon

CONFIG_FILE = "config.json"

def get_manager_id():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                manager_id = data.get("manager_id")
                if manager_id:
                    return str(manager_id)
        except Exception:
            pass

    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    text, ok = QInputDialog.getText(
        None, 
        "Авторизация виджета", 
        "Введите ваш ID менеджера из Битрикс24:"
    )

    if ok and text.strip():
        manager_id = text.strip()
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"manager_id": manager_id}, f, ensure_ascii=False, indent=4)
            return manager_id
        except Exception as e:
            QMessageBox.critical(None, "Ошибка", f"Не удалось сохранить config.json: {e}")
            sys.exit(1)
    else:
        sys.exit(0)

class WebSocketWorker(QThread):
    call_received = pyqtSignal(dict)

    def __init__(self, manager_id):
        super().__init__()
        self.manager_id = manager_id
        self.running = True
        self.websocket = None
        self.loop = None 

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.listen_websocket())

    async def listen_websocket(self):
        uri = f"ws://194.58.95.53:8082/ws/{self.manager_id}"
        while self.running:
            try:
                async with websockets.connect(uri) as websocket:
                    self.websocket = websocket
                    print(f"[WebSocket] Подключено к серверу для менеджера {self.manager_id}")
                    while self.running:
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                            data = json.loads(message)
                            self.call_received.emit(data)
                        except asyncio.TimeoutError:
                            continue 
                        except json.JSONDecodeError:
                            print("[WebSocket] Ошибка JSON")
            except Exception as e:
                if self.running:
                    print(f"[WebSocket] Ошибка сети: {e}. Повтор через 5 сек...")
                    try:
                        await asyncio.sleep(5)
                    except asyncio.CancelledError:
                        break

    def stop(self):
        self.running = False
        if self.websocket and self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.websocket.close(), self.loop)
        
        self.quit()
        if not self.wait(1500): 
            self.terminate()


class SummaPlusWidget(QWidget):
    def __init__(self, manager_id): 
        super().__init__()
        self.manager_id = manager_id 
        self.product_labels = [] # ФИКС: Инициализируем список для хранения ссылок на QLabel товаров
        self.init_ui()
        
        self.worker = WebSocketWorker(self.manager_id)
        self.worker.call_received.connect(self.update_widget_data)
        self.worker.start()
    
    def init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(650, 420)
        
        main_frame = QFrame(self)
        main_frame.setObjectName("MainFrame")
        main_frame.setFixedSize(630, 390)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 6)
        main_frame.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(main_frame)
        layout.setContentsMargins(0, 0, 0, 16)
        layout.setSpacing(0)
        
        header = QFrame()
        header.setObjectName("Header")
        header.setFixedHeight(60)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        
        status_label = QLabel("📞 ВХОДЯЩИЙ ЗВОНОК")
        status_label.setObjectName("StatusLabel")
        
        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseBtn")
        close_btn.clicked.connect(self.close)
        
        header_layout.addWidget(status_label)
        header_layout.addStretch()
        header_layout.addWidget(close_btn)
        layout.addWidget(header)
        
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 18, 20, 0)
        content_layout.setSpacing(8)
        
        self.company_name = QLabel("Ожидание входящего вызова...")
        self.company_name.setObjectName("CompanyName") 
        content_layout.addWidget(self.company_name)   

        info_layout = QHBoxLayout()
        self.manager_label = QLabel("Менеджер: Загрузка...")
        self.manager_label.setObjectName("SubText")

        self.status_badge = QLabel(" Ожидание ")
        self.status_badge.setObjectName("StatusBadge") 

        info_layout.addWidget(self.manager_label) 
        info_layout.addStretch()
        info_layout.addWidget(self.status_badge) 
        content_layout.addLayout(info_layout)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("Separator")
        content_layout.addWidget(line)
        
        content_layout.addStretch()
        
        scroll_area = QScrollArea()
        scroll_area.setObjectName("DangerScroll")
        scroll_area.setWidgetResizable(True) 
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff) 
        
        danger_zone = QFrame()
        danger_zone.setObjectName("DangerZone")
        self.danger_layout = QVBoxLayout(danger_zone)
        self.danger_layout.setContentsMargins(16, 14, 16, 14)
        self.danger_layout.setSpacing(8) 
        
        danger_title = QLabel("⚠️ ПРЕДЛОЖИТЬ В ТЕКУЩЕМ КАСАНИИ (НЕТ ОТГРУЗОК):")
        danger_title.setObjectName("DangerTitle")
        self.danger_layout.addWidget(danger_title)
        
        scroll_area.setWidget(danger_zone)
        content_layout.addWidget(scroll_area)
        layout.addLayout(content_layout)

        self.setStyleSheet("""
            #MainFrame {
                background-color: #FFFFFF;
                border-radius: 16px;
            }
            #Header {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #F9D066, stop:1 #E6B333);
                border-top-left-radius: 16px;
                border-top-right-radius: 16px;
            }
            #StatusLabel {
                color: #232323;
                font-size: 15px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            #CloseBtn {
                background: transparent;
                color: #232323;
                border: none;
                font-size: 20px;
                font-weight: bold;
            }
            #CloseBtn:hover {
                color: #8F0000;
            }
            #CompanyName {
                color: #1A1A1A;
                font-size: 22px;
                font-weight: bold;
            }
            #SubText {
                color: #666666;
                font-size: 15px;
            }
            #StatusBadge {
                background-color: #9E9E9E; 
                color: #FFFFFF;            
                font-size: 15px;           
                font-weight: bold;
                border-radius: 6px;
                padding: 5px 12px;         
            }
            #Separator {
                color: #EAEAEA;
                max-height: 1px;
                margin-top: 5px;
            }
            #DangerScroll {
                border: 1px solid #FFCCCC;
                border-radius: 10px;
                background-color: #FFF5F5;
            }
            #DangerZone {
                background-color: #FFF5F5;
                border: none;
            }
            #DangerTitle {
                color: #CC0000;
                font-size: 13px;
                font-weight: bold;
                margin-bottom: 4px;
            }
            #DangerItem {
                color: #232323;
                font-size: 15px;
                font-weight: 500;
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 6px;
                margin: 4px 2px 4px 0px;
            }
            QScrollBar::handle:vertical {
                background: #FFAAAA;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #FF8888;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        self.position_widget()

    def position_widget(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.width() - self.width() - 10
        y = screen.height() - self.height() - 10
        self.move(x, y)

    def update_widget_data(self, data):
        self.company_name.setText(data.get("company_name", "Неизвестная компания"))
        new_status = data.get("company_status", "Действующий")
        self.status_badge.setText(f" {new_status} ")
        
        new_manager = data.get("manager_name", "Не указан")
        self.manager_label.setText(f"Менеджер: {new_manager}")
        
        # Полная очистка старой матрицы товаров
        for label in self.product_labels:
            self.danger_layout.removeWidget(label)
            label.deleteLater()
        self.product_labels.clear()
        
        # Удаляем старые пружины из разметки, если они там оставались
        while self.danger_layout.count() > 1:
            item = self.danger_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        
        # Отрисовка нового свежего ассортимента из сети
        red_cells = data.get("red_cells", [])
        if not red_cells:
            no_items_label = QLabel("• Нет критических просадок по матрице")
            no_items_label.setStyleSheet("color: #27ae60; font-style: italic;")
            self.danger_layout.addWidget(no_items_label)
            self.product_labels.append(no_items_label)
        else:
            for item in red_cells:
                item_label = QLabel(f"• {item}")
                item_label.setObjectName("DangerItem")
                item_label.setWordWrap(True)
                self.danger_layout.addWidget(item_label)
                self.product_labels.append(item_label)
        
        self.danger_layout.addStretch()
        
        # ФИКС СКРЫТИЯ ОКНА: Принудительный сброс и поднятие флагов + фокус в OS Windows
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.position_widget()
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        print("[Widget] Закрытие приложения. Остановка WebSocket-потока...")
        self.worker.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    current_manager_id = get_manager_id()
    widget = SummaPlusWidget(manager_id=current_manager_id)
    widget.show()
    sys.exit(app.exec())

