import requests
import json

# 1. Задаем город
city_name = input("Введите город: ")  

# 2. ГЕОКОДИРОВНИЕ
geo_url = "https://geocoding-api.open-meteo.com/v1/search"
geo_params = {
    "name": city_name,
    "count": 1,            # Берем первое совпадение по городу
    "langage": "en",
    "format": "json"
}

geo_response = requests.get(geo_url, params=geo_params) 
geo_data = geo_response.json()

# Проверяем, нашелся ли город
if "results" in geo_data :
    location = geo_data["results"][0]
    lat = location["latitude"]
    lon = location["longitude"]

    print(f"Город найден: {location['name']}, координаты: {lat}, {lon}")

# 3. ЗАПРОС ПОГОДЫ
weather_url = "https://api.open-meteo.com/v1/forecast"
weather_params = {
    "latitude": lat,    
    "longitude": lon,
    "current": "temperature_2m",   
    "timezone": "auto"
}
weather_response = requests.get(weather_url, params = weather_params)
weather_data = weather_response.json()

# 4. Сохранение в файл
with open('weather_data.json', 'w', encoding ='utf-8') as f :
    json.dump(weather_data, f, ensure_ascii=False, indent=4)

    # Вывод результата на консоль
    temp = weather_data["current"]["temperature_2m"]

    print(f"Текущая температура: {temp} °C")
