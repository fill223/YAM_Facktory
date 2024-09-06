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


# Прокси
proxies = [
    "45.134.183.45", "212.115.49.249", "45.142.252.216", "77.83.84.29",
    "194.156.92.171", "109.248.167.172", "193.58.169.116", "45.142.253.62", "95.182.126.104",
    "45.11.21.238", "45.139.177.225", "46.8.56.208", "45.142.253.80", "45.140.54.57",
    "45.134.181.106", "178.250.190.235", "109.68.210.50", "194.33.39.30", "45.89.102.249",
    "194.33.36.121", "45.88.148.157", "45.83.117.254", "109.107.180.139", "141.98.133.254",
    "109.107.180.101", "31.12.92.63", "185.166.163.4", "45.92.124.174", "45.92.125.19"
]

file_path = '4if71yywt6.txt'

# Чтение куков из файла
with open(file_path, 'r', encoding='utf-8') as file:
    content = file.read()

# Разделение на блоки куков по пустой строке
accounts = [block for block in content.split("\n") if block.strip()]
profiles = []


for i in range(21):
    # Извлечение данных из строки
    line = accounts[i].strip().split(':')
    
    # Извлечение имени профиля до знака '@'
    email = line[0]
    profile_name = email.split('@')[0]  # Извлекаем часть строки до символа '@'
    
    # Прокси
    proxy_ip = proxies[i]
    proxy = {
        "mode": "http",
        "host": proxy_ip,
        "port": 3000,
        "username": "6MFqGQ",
        "password": "ItalianOzz100"
    }
    
    # Настройки профиля
    profile = {
        "name": profile_name,
        "folder": "New",  # Указание папки, в которую следует добавить профиль
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
