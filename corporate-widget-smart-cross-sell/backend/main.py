import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Dict, Optional, List

# Новое название проекта
app = FastAPI(title="Corporate Widget Backend")

N8N_API_KEY = "youself_APY_KEY"

class CallPayload(BaseModel):
    manager_id: str          
    manager_name: str        # ФИКС: Добавили поле для имени менеджера, которое шлет n8n
    company_name: str       
    company_status: str = "Действующий"  
    red_cells: List[str]    

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
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(manager_id)

# n8n шлет POST-запрос на: http://194.58.95.53:8082/api/v1/call-event
@app.post("/api/v1/call-event", dependencies=[Depends(verify_n8n_token)])
async def handle_call_event(payload: CallPayload):
    event_data = payload.model_dump()
    
    # ЛОГИРОВАНИЕ ДЛЯ ШАГА 1: Выводим в консоль VPS всё от n8n
    print("\n=== ВХОДЯЩИЙ ВЕБХУК ОТ N8N ===")
    print(f"ID менеджера: {payload.manager_id}")
    print(f"Имя менеджера: {payload.manager_name}")
    print(f"Компания: {payload.company_name}")
    print(f"Статус Б24: {payload.company_status}")
    print(f"Просадки ассортимента: {payload.red_cells}")
    print("==============================\n")

    success = await manager.send_personal_message(payload.manager_id, event_data)
    
    if success:
        return {"status": "success", "message": f"Данные доставлены менеджеру {payload.manager_id}"}
    else:
        return {"status": "ignored", "message": f"Менеджер {payload.manager_id} сейчас оффлайн"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8082)

