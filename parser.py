import time
import sys
import os
import configparser
import requests
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from gologin import GoLogin

# Load configuration from config.ini
config = configparser.ConfigParser()
config.read('config.ini')

API_KEY = config['gologin']['api_key']
SITE_URL = config['gologin']['site_url']
BASE_URL = 'https://api.gologin.com/browser/v2'

# Logging Utilities
def suppress_gologin_logs():
    """Suppresses GoLogin logs."""
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')

def enable_logs():
    """Enables standard logging."""
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__

# GoLogin API Interactions
def get_profiles(api_key):
    """Fetches the list of profiles from GoLogin using the provided API key."""
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    response = requests.get(BASE_URL, headers=headers)
    response.raise_for_status()
    return response.json()

def start_selenium_with_profile(profile_id, api_key):
    """Starts Selenium WebDriver with a specified GoLogin profile."""
    suppress_gologin_logs()
    gl = GoLogin({
        "token": api_key,
        "profile_id": profile_id,
    })

    debugger_address = gl.start()
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", debugger_address)
    
    # Specify the path to the downloaded ChromeDriver
    chrome_driver_path = 'C:\\Lichnoe\\Fucktory\\chromedriver-win64\\chromedriver.exe'
    service = ChromeService(executable_path=chrome_driver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    enable_logs()
    return driver, gl

def iterate_pickup_points(driver):
    """Перебирает все доступные пункты выдачи."""
    try:
        # 1. Открываем выпадающий список пунктов выдачи
        WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((By.ID, "hyperlocation-unified-dialog-anchor"))
        ).click()
        print("Открыли выпадающий список пунктов выдачи.")

        # 2. Ожидаем появления всех элементов ПВЗ
        WebDriverWait(driver, 2).until(
            EC.presence_of_all_elements_located((By.XPATH, "//div[@aria-label='Выбрать адрес доставки']"))
        )
        print("Элементы пунктов выдачи загружены.")

        # 3. Получаем все элементы пунктов выдачи с текстом "Пункт выдачи" или "7 дней хранения"
        pickup_points = driver.find_elements(By.XPATH, "//div[@aria-label='Выбрать адрес доставки' and (contains(., 'Пункт выдачи') or contains(., '7 дней хранения'))]")

        for i in range(len(pickup_points)):
            try:
                # Повторный поиск элемента для предотвращения stale element reference exception
                pickup_points = driver.find_elements(By.XPATH, "//div[@aria-label='Выбрать адрес доставки' and (contains(., 'Пункт выдачи') or contains(., '7 дней хранения'))]")
                if i >= len(pickup_points):
                    print("Индекс вышел за пределы списка элементов.")
                    continue
                
                point = pickup_points[i]

                # Извлечение текста адреса для отладки
                point_address = point.text.strip()

                # Прокрутка к элементу и клик по нему с помощью JavaScript
                driver.execute_script("arguments[0].scrollIntoView();", point)
                time.sleep(1)  # Пауза для прокрутки

                # Используем JavaScript для клика по элементу
                driver.execute_script("arguments[0].click();", point)
                print(f"Выбрали пункт выдачи: {point_address}")
                time.sleep(3)  # Ждем завершения действия

            except Exception as e:
                print(f"Не удалось обработать пункт: {e}")

    except Exception as e:
        print(f"Ошибка при переборе пунктов выдачи: {e}")

def run_profiles(api_key):
    """Runs the scraping process across all GoLogin profiles."""
    print("Программа запустилась")
    profiles = get_profiles(api_key)
    profile_count = len(profiles['profiles'])
    print(f"Нашел {profile_count} профилей")

    if 'profiles' in profiles:
        for profile in profiles['profiles']:
            profile_id = profile['id']
            profile_name = profile['name']
            print(f"Открываю профиль {profile_name}, id {profile_id}")
            driver, gl = start_selenium_with_profile(profile_id, api_key)
            driver.get(SITE_URL)
            print("Открываю ссылку")
            time.sleep(2)
            
            try:
                # Перебираем пункты выдачи
                iterate_pickup_points(driver)

            except Exception as e:
                print(f"Ошибка при обработке товара: {e}")
            
            time.sleep(2)

            driver.quit()
            suppress_gologin_logs()
            gl.stop()
            enable_logs()
    else:
        print("Unexpected response structure:", profiles)

def main():
    """Main entry point for the program."""
    try:
        run_profiles(API_KEY)
    except requests.exceptions.HTTPError as err:
        print(f"HTTP error occurred: {err}")
    except Exception as err:
        print(f"An error occurred: {err}")

if __name__ == "__main__":
    main()
