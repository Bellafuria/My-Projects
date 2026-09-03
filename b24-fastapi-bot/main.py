import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, Request, BackgroundTasks
import requests
import os

app = FastAPI()

# НАСТРОЙКИ ПОЧТЫ (VK WorkSpace / Mail.ru)
SMTP_SERVER = "smtp.mail.ru"
SMTP_PORT = 587  # Использование STARTTLS для обхода блокировок портов хостинга

# Защита данных: берем доступы из переменных окружения сервера, либо используем заглушки
SMTP_USER = os.getenv("SMTP_USER", "your_login@domain.com")  
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "your_secure_app_password")  

# СПИСОК ПОЛУЧАТЕЛЕЙ УВЕДОМЛЕНИЙ
RECIPIENTS = [
    "manager1@domain.com",
    "manager2@domain.com"
]

# ССЫЛКА НА ВХОДЯЩИЙ ВЕБХУК БИТРИКС24
B24_WEBHOOK_URL = os.getenv("B24_WEBHOOK_URL", "https://bitrix24.ru")

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

def send_email_notification(lead_id: str, lead_title: str, source_id: str, responsible_person: str):
    """Формирование и отправка HTML-письма через SMTP-сервер"""
    # Динамическое формирование ссылки на лид в CRM
    crm_domain = B24_WEBHOOK_URL.split("/rest/")[0]  # Автоматически вырезает домен Битрикс24
    lead_url = f"{crm_domain}/crm/lead/details/{lead_id}/"
    
    subject = f"🔥 Новый Лид в CRM! ID: {lead_id}"
    
    html_content = f"""
    <html>
        <body>
            <h2>Поступил новый лид на обработку!</h2>
            <p><b>Название лида:</b> {lead_title}</p>
            <p><b>Источник:</b> {source_id}</p>
            <p><b>Ответственный:</b> {responsible_person}</p>
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
            
            # Извлекаем ID ответственного и запрашиваем его текстовое имя
            user_id = lead_data.get("ASSIGNED_BY_ID")
            responsible_person = get_user_name(user_id)
            
            # Фильтр источника: обрабатываем только заявки с Веб-сайта (код "WEB")
            if source_id in ["WEB", "Веб-сайт"]:
                # Асинхронный запуск отправки в бэкграунде для моментального ответа серверу CRM
                background_tasks.add_task(send_email_notification, lead_id, lead_title, source_id, responsible_person)
                return {"status": "success", "message": "Notification task scheduled"}
                
    return {"status": "ignored"}

@app.get("/test")
def test_route():
    return {"status": "FastAPI integration server is online!"}

