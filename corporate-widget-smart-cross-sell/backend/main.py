import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Dict, Optional, List

# Новое название проекта
app = FastAPI(title="Corporate Widget Backend")

N8N_API_KEY = "super_secret_n8n_token_2026"

# КЭШ В ОПЕРАТИВНОЙ ПАМЯТИ ДЛЯ МАТРИЦЫ 1С
cached_matrix_1c: Dict[str, Dict[str, List[dict]]] = {}

# Модель для утреннего обновления кэша матрицы из n8n
class MatrixPayload(BaseModel):
    matrix: dict

# Модель события звонка из n8n
class CallPayload(BaseModel):
    manager_id: str          
    manager_name: str        
    company_name: str       
    clean_company_name: str  # Будем получать очищенное имя для поиска на бэкенде
    company_status: str = "Действующий"   

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, manager_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[manager_id] = websocket
        print(f"👨‍💻 Менеджер {manager_id} успешно подключился к виджету")

    def disconnect(self, manager_id: str):
        if manager_id in self.active_connections:
            del self.active_connections[manager_id]
            print(f"❌ Менеджер {manager_id} отключился")

    async def send_personal_message(self, manager_id: str, data: dict) -> bool:
        websocket = self.active_connections.get(manager_id)
        if websocket:
            try:
                await websocket.send_json(data)
                return True
            except Exception as e:
                print(f"⚠️ Ошибка отправки менеджеру {manager_id}: {e}")
                self.disconnect(manager_id)
                return False
        return False

manager = ConnectionManager()

def verify_n8n_token(x_api_key: Optional[str] = Header(None)):
    if x_api_key != N8N_API_KEY:
        raise HTTPException(status_code=403, detail="Неверный или отсутствующий API-ключ")

@app.websocket("/ws/{manager_id}")
async def websocket_endpoint(websocket: WebSocket, manager_id: str):
    await manager.connect(manager_id, websocket)
    try:
        while True:
            # Заменено на receive_bytes, чтобы uvicorn на бэкенде автоматически 
            # перехватывал и обрабатывал системные пинг-фреймы от виджета
            await websocket.receive_bytes()
    except WebSocketDisconnect:
        manager.disconnect(manager_id)
    except Exception as e:
        # Добавлен перехват скрытых сетевых ошибок, чтобы вовремя очищать manager.active_connections
        print(f"⚠️ Сетевое исключение на сокете менеджера {manager_id}: {e}")
        manager.disconnect(manager_id)

# ЭНДПОИНТ ДЛЯ ОБНОВЛЕНИЯ УТРЕННЕГО КЭША МАТРИЦЫ 1С
# Сюда n8n будет отправлять POST-запрос с токеном в заголовке X-API-Key
@app.post("/api/v1/update-matrix", dependencies=[Depends(verify_n8n_token)])
async def update_matrix(payload: MatrixPayload):
    global cached_matrix_1c
    cached_matrix_1c = payload.matrix
    print(f"\n🔄 [FastAPI] Матрица 1С успешно закэширована.")
    print(f"Загружено менеджеров из 1С: {len(cached_matrix_1c)}\n")
    return {"status": "success", "message": "Матрица 1С успешно закэширована"}

# ОБНОВЛЕННЫЙ ЭНДПОИНТ ОБРАБОТКИ ЗВОНКА
@app.post("/api/v1/call-event", dependencies=[Depends(verify_n8n_token)])
async def handle_call_event(payload: CallPayload):
    global cached_matrix_1c
    
    search_title = payload.clean_company_name.lower().strip()
    red_cells = []

        # Универсальный поиск компании без жесткой привязки к типу данных (dict/list)
    for manager_key, clients in cached_matrix_1c.items():
        # Если клиенты представлены в виде словаря
        if isinstance(clients, dict):
            for client_name, products in clients.items():
                if client_name.lower().strip() == search_title:
                    if isinstance(products, list):
                        red_cells = [p.get("productName") for p in products if isinstance(p, dict) and "productName" in p]
                    break
        # Если клиенты прилетели в виде списка словарей (особенность парсинга n8n)
        elif isinstance(clients, list):
            for client_item in clients:
                if isinstance(client_item, dict):
                    for client_name, products in client_item.items():
                        if client_name.lower().strip() == search_title:
                            if isinstance(products, list):
                                red_cells = [p.get("productName") for p in products if isinstance(p, dict) and "productName" in p]
                            break
        if red_cells:
            break  # Если товары нашли, останавливаем перебор менеджеров




    # Собираем итоговый пакет, который ждёт PyQt6 виджет (с полем red_cells)
    event_data = {
        "manager_id": payload.manager_id,
        "manager_name": payload.manager_name,
        "company_name": payload.company_name,
        "company_status": payload.company_status,
        "red_cells": red_cells
    }
    
    print("\n=== ВХОДЯЩИЙ ВЕБХУК ОТ N8N ===")
    print(f"ID менеджера: {payload.manager_id}")
    print(f"Имя менеджера: {payload.manager_name}")
    print(f"Компания: {payload.company_name} (Поиск по: '{search_title}')")
    print(f"Статус Б24: {payload.company_status}")
    print(f"Найдено просадок на бэкенде: {len(red_cells)}")
    print("==============================\n")

    success = await manager.send_personal_message(payload.manager_id, event_data)
    
    if success:
        return {"status": "success", "message": f"Данные доставлены менеджеру {payload.manager_id}", "found_items": len(red_cells)}
    else:
        return {"status": "ignored", "message": f"Менеджер {payload.manager_id} сейчас оффлайн", "found_items": len(red_cells)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8082)

