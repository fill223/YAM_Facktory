import configparser
import time
from multiprocessing import Pool
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from gologin import GoLogin
import requests
import shutil
import os

# Чтение конфигурации из config.ini
config = configparser.ConfigParser()
config.read('config.ini')

# Данные из конфиг файла
API_KEY = config.get('gologin', 'api_key')
SITE_URL = config.get('gologin', 'site_url')
PROFILE_FOLDER = config.get('gologin', 'profile_folder')
PROFILE_URL = config.get('gologin', 'profile_url')

CHROME_DRIVER_PATH = config.get('selenium', 'chrome_driver_path')
MAX_WORKERS = config.getint('selenium', 'max_workers')
AMOUNT_OF_PROFILES = config.getint('selenium', 'amount_of_profiles')

# Функция для запуска профиля через GoLogin API
def start_gologin_profile(profile_id):
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    
    url = f"https://api.gologin.com/browser/{profile_id}/run"
    
    # Тело запроса, которое запускает профиль
    body = {
        "running": True,
        "type": "desktop",
        "googleClientId": "string"
    }
    
    response = requests.patch(url, headers=headers, json=body)
    
    if response.status_code == 200:
        data = response.json()
        debugger_url = data.get('wsUrl')  # Получаем URL для подключения через WebSocket
        return debugger_url
    else:
        raise Exception(f"Failed to start GoLogin profile: {response.status_code}, {response.text}")

# Основная функция для парсинга
def scrap(profile):
    try:
        # Запускаем профиль через GoLogin API
        debugger_address = start_gologin_profile(profile['profile_id'])
        
        # Настройка ChromeOptions для подключения к запущенному профилю
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", debugger_address)

        # Использование Service для указания пути к ChromeDriver
        service = Service(executable_path=CHROME_DRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # Переход на сайт
        driver.get(SITE_URL)

        # Ожидание загрузки страницы
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "content"))  # Подстройка по нужному элементу
        )

        # Вывод заголовка и URL страницы
        print('Page title:', driver.title)
        print('Page URL:', driver.current_url)  # Возвращаем или выводим URL текущей страницы

        # Возврат URL для дальнейшего использования
        return driver.current_url

    except Exception as e:
        print(f"Error with profile {profile['profile_id']}: {str(e)}")

    finally:
        if 'driver' in locals():
            print('closing', profile['profile_id'])
            driver.quit()

        # Ожидание завершения работы Chrome
        time.sleep(5)
        
        # Остановка профиля и обработка ошибок
        try:
            gl = GoLogin({
                'token': API_KEY,
                'profile_id': profile['profile_id'],
                'port': profile['port']
            })
            gl.stop()
        except PermissionError as e:
            print(f"PermissionError: Unable to delete profile for {profile['profile_id']}: {e}")
        except Exception as e:
            print(f"Error while stopping GoLogin profile {profile['profile_id']}: {e}")


if __name__ == '__main__':
    # Функция для получения профилей с GoLogin API
    def fetch_profiles(api_key, amount):
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        response = requests.get('https://api.gologin.com/browser/v2', headers=headers)
        if response.status_code == 200:
            profiles = response.json().get('profiles', [])
            return [{'profile_id': profile['id'], 'port': 3500 + idx} for idx, profile in enumerate(profiles[:amount])]
        else:
            print(f"Failed to fetch profiles: {response.status_code}")
            return []

    profiles = fetch_profiles(API_KEY, AMOUNT_OF_PROFILES)

    if profiles:
        with Pool(MAX_WORKERS) as p:
            results = p.map(scrap, profiles)

        # Вывод всех полученных URL
        print("All scraped URLs:", results)
    else:
        print("No profiles found.")
