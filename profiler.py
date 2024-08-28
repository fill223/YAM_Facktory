import requests
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Настройка Selenium для автоматического получения userAgent
options = webdriver.ChromeOptions()
options.add_argument("--headless")  # Запуск без интерфейса браузера

# Инициализация драйвера Chrome
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Получение актуального userAgent
driver.get("https://www.whatismybrowser.com/")
user_agent = driver.execute_script("return navigator.userAgent;")
driver.quit()

print(f'Актуальный userAgent: {user_agent}')

# Ваш API-токен от GoLogin
api_token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2Njk3ZmE3YTVkNDE2NWYxODhjYTYxZTIiLCJ0eXBlIjoiZGV2Iiwiand0aWQiOiI2NmIwZTk3NWMwMThmZTc3NDZiMWVjNWMifQ.uRqwyYNtuiW2tbMa8pjgwGYrwYbo3LvITNSxnF9IWzU'


# URL для работы с профилями GoLogin
base_url = 'https://api.gologin.com'

# Чтение аккаунтов из файла
with open('accounts.txt', 'r') as file:
    accounts = file.readlines()

# Прокси
proxies = [
    "45.135.33.217", "45.147.192.25", "193.53.168.201", "46.8.223.189", "46.8.16.87",
    "141.98.135.11", "194.33.37.142", "194.33.39.134", "185.149.20.115", "31.12.94.243",
    "176.53.186.199", "45.139.177.44", "45.134.253.176", "95.182.126.178", "45.134.180.83",
    "45.92.125.40", "31.12.93.233", "92.119.41.177", "92.119.40.2", "92.119.43.75",
    "45.135.33.85", "45.15.237.162", "84.54.53.185", "45.134.181.117", "84.54.53.186",
    "45.83.117.217", "45.83.116.6", "178.250.190.240", "185.149.23.134", "141.98.133.232"
]

# Подготовка профилей для создания
profiles = []

for i in range(29):
    # Извлечение данных из строки
    line = accounts[i].strip().split(':')
    profile_name = f"{line[0]}:{line[1]}"
    
    # Прокси
    proxy_ip = proxies[i]
    proxy = {
        "mode": "http",
        "host": proxy_ip,
        "port": 3000,
        "username": "l238cc",
        "password": "hw3oYBSCz6"
    }
    
    # Настройки профиля
    profile = {
        "name": profile_name,
        "proxyEnabled": True,
        "proxy": proxy,
        "navigator": {
            "language": "en-US",
            "resolution": "1024x768",
            "platform": "win",
            "userAgent": user_agent  # Использование актуального userAgent
        },
        "browserType": "chrome",
        "os": "win"
    }
    
    profiles.append(profile)

# Создание профилей
for profile in profiles:
    response = requests.post(
        f'{base_url}/browser',
        headers={'Authorization': f'Bearer {api_token}', 'Content-Type': 'application/json'},
        data=json.dumps(profile)
    )
    
    if response.status_code == 201:
        print(f'Профиль {profile["name"]} успешно создан.')
    else:
        print(f'Ошибка при создании профиля {profile["name"]}: {response.status_code} - {response.text}')
