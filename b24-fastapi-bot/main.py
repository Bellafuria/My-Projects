import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, Request, BackgroundTasks
import requests
import os

app = FastAPI()

# НАСТРОЙКИ ПОЧТЫ (VK WorkSpace / Mail.ru)
SMTP_SERVER = "smtp.mail.ru"
SMTP_PORT = 587

# Защита данных: берем доступы из переменных окружения сервера
SMTP_USER = os.getenv("SMTP_USER", "your_login@domain.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "your_secure_app_password")

# СПИСОК ПОЛУЧАТЕЛЕЙ УВЕДОМЛЕНИЙ
RECIPIENTS = [
    "manager1@domain.com",
    "manager2@domain.com",
    "manager3@domain.com"
]

# ССЫЛКА НА ВХОДЯЩИЙ ВЕБХУК БИТРИКС24
B24_WEBHOOK_URL = os.getenv("B24_WEBHOOK_URL", "https://your-domain.bitrix24.ru/rest/1/your_webhook_key/")

# ID менеджеров (пример)
manager1_ID = N
manager2_ID = N
manager3_ID = N

# Простой счётчик в памяти
buy_counter = 0

def get_next_buy_assignee():
    global buy_counter
    buy_counter += 1
    return manager1_ID if buy_counter % 2 == 1 else manager2_ID

def update_lead_assignee(lead_id: str, user_id: int):
    """Обновляет ответственного в лиде"""
    url = f"{B24_WEBHOOK_URL}crm.lead.update.json"
    try:
        requests.post(url, json={
            "id": lead_id,
            "fields": {"ASSIGNED_BY_ID": user_id}
        }, timeout=10)
        print(f"Лид {lead_id} назначен на пользователя {user_id}")
    except Exception as e:
        print(f"Ошибка обновления ответственного: {e}")

def get_lead_info(lead_id: str):
    """Запрос детальной информации о лиде из Битрикс24 REST API"""
    url = f"{B24_WEBHOOK_URL}crm.lead.get.json"
    try:
        response = requests.get(url, params={"id": lead_id})
        if response.status_code == 200:
            return response.json().get("result", {})
    except Exception as e:
        print(f"Ошибка запроса к Б24: {e}")
    return None

def get_user_name(user_id: str):
    """Запрос имени ответственного сотрудника из Битрикс24 по его ID"""
    if not user_id:
        return "Не назначен"
    url = f"{B24_WEBHOOK_URL}user.get.json"
    try:
        response = requests.get(url, params={"ID": user_id})
        if response.status_code == 200:
            result_data = response.json().get("result", [])
            if result_data and len(result_data) > 0:
                user_data = result_data[0]
                name = user_data.get("NAME", "")
                last_name = user_data.get("LAST_NAME", "")
                return f"{name} {last_name}".strip() or f"ID {user_id}"
    except Exception as e:
        print(f"Ошибка запроса имени пользователя: {e}")
    return f"ID {user_id}"

def send_email_notification(lead_id: str, lead_title: str, source_id: str, responsible_person: str, assigned_to_name: str = ""):
    """Формирование и отправка HTML-письма через SMTP-сервер"""
    crm_domain = B24_WEBHOOK_URL.split("/rest/")[0]
    lead_url = f"{crm_domain}/crm/lead/details/{lead_id}/"
    
    subject = f"Новый Лид в CRM! ID: {lead_id}"
    
    assignment_note = f"<p><b>Назначен на:</b> {assigned_to_name}</p>" if assigned_to_name else ""
    
    html_content = f"""
    <html>
        <body>
            <h2>Поступил новый лид на обработку!</h2>
            <p><b>Название лида:</b> {lead_title}</p>
            <p><b>Источник:</b> {source_id}</p>
            <p><b>Ответственный:</b> {responsible_person}</p>
            {assignment_note}
            <p><b>Ссылка в CRM:</b> <a href="{lead_url}">{lead_url}</a></p>
        </body>
    </html>
    """
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            
            for recipient in RECIPIENTS:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = SMTP_USER
                msg["To"] = recipient
                msg.attach(MIMEText(html_content, "html", "utf-8"))

                server.sendmail(SMTP_USER, recipient, msg.as_string())
                print(f"Письмо успешно отправлено на {recipient}")
    except Exception as e:
        print(f"Ошибка отправки почты (SMTP блок): {e}")

@app.post("/webhook")
async def bitrix_webhook(request: Request, background_tasks: BackgroundTasks):
    """Прием и валидация входящего вебхука от Битрикс24"""
    form_data = await request.form()
    data = dict(form_data)
    
    lead_id = data.get("data[FIELDS][ID]")
    event = data.get("event")
    
    if event == "ONCRMLEADADD" and lead_id:
        lead_data = get_lead_info(lead_id)
        if lead_data:
            lead_title = lead_data.get("TITLE", "Без названия")
            source_id = lead_data.get("SOURCE_ID", "Не указан")
            
            # Читаем поле "Вы хотите"
            want_value = lead_data.get("ID_CRM_field", "")

            assignee_id = None
            assigned_to_name = ""

            if want_value == "VALUE1":
                assignee_id = manager3_ID
                assigned_to_name = "manager3"
            elif want_value == "VALUE2":
                assignee_id = get_next_buy_assignee()
                assigned_to_name = "manager1" if assignee_id == manager1_ID else "manager2"

            # Обновляем ответственного в лиде
            if assignee_id:
                update_lead_assignee(lead_id, assignee_id)
                responsible_person = get_user_name(str(assignee_id))
            else:
                user_id = lead_data.get("ASSIGNED_BY_ID")
                responsible_person = get_user_name(user_id)
            
            # Фильтр источника: обрабатываем только заявки с Веб-сайта
            if source_id in ["WEB", "Веб-сайт"]:
                background_tasks.add_task(
                    send_email_notification,
                    lead_id,
                    lead_title,
                    source_id,
                    responsible_person,
                    assigned_to_name
                )
                return {"status": "success", "message": "Notification task scheduled"}
                
    return {"status": "ignored"}

@app.get("/test")
def test_route():
    return {"status": "FastAPI integration server is online!"}