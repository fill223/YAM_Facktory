import os
import configparser
import requests
from selenium import webdriver
from concurrent.futures import ThreadPoolExecutor
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from gologin import GoLogin
import shutil
import re
import time

# Загрузка конфигурации из config.ini
config = configparser.ConfigParser()
config.read('config.ini')

# Чтение параметров из конфигурационного файла
API_KEY = config['gologin']['api_key']
SITE_URL = config['gologin']['site_url']
CHROME_DRIVER_PATH = config['selenium']['chrome_driver_path']
MAX_WORKERS = config.getint('selenium', 'max_workers')
PROFILE_FOLDER = config['gologin']['profile_folder']  # Получение папки профилей из конфигурации
BASE_URL = 'https://api.gologin.com/browser/v2'

def get_profiles(api_key, folder):
    """Получает список профилей из GoLogin с использованием предоставленного API ключа и указанной папки."""
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(f"{BASE_URL}?folder={folder}", headers=headers)  # Использование папки из конфигурации
        response.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return None
    except Exception as err:
        print(f"Other error occurred: {err}")
        return None

    return response.json()

def start_selenium_with_profile(profile_id, api_key):
    """Запускает Selenium WebDriver с указанным профилем GoLogin в headless режиме."""
    try:
        gl = GoLogin({
            "token": api_key,
            "profile_id": profile_id,
            "extra_params": {
                "autoHeadless": True  # Включаем headless режим через GoLogin API
            }
        })

        # Запускаем профиль GoLogin и получаем адрес отладчика
        debugger_address = gl.start()

        # Настройка Chrome options для headless режима
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Включаем headless режим
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_experimental_option("debuggerAddress", debugger_address)

        # Используем уникальную временную директорию данных пользователя для каждого экземпляра
        temp_user_data_dir = os.path.join('C:\\TempProfiles', f"chrome_profile_{profile_id}")
        os.makedirs(temp_user_data_dir, exist_ok=True)
        chrome_options.add_argument(f"--user-data-dir={temp_user_data_dir}")

        # Указываем путь к загруженному ChromeDriver
        service = ChromeService(executable_path=CHROME_DRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=chrome_options)

        return driver, gl, temp_user_data_dir

    except Exception as e:
        print(f"Failed to start Selenium WebDriver for profile {profile_id}: {e}")
        raise

def extract_price(driver):
    """Извлекает цену с текущей страницы."""
    try:
        price_element = WebDriverWait(driver, 10, poll_frequency=0.2).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "h3[data-auto='snippet-price-current']"))
        )
        price = price_element.text.strip()
        price = re.sub(r'[^\d,]', '', price)  # Удаляем все, кроме цифр и запятых
        price_float = float(price.replace(',', '.'))

        return price_float
    except Exception as e:
        return float('inf')  # Используем 'inf' для невозможных цен

def clean_pickup_point_address(raw_text):
    """Очищает текст пункта выдачи, оставляя только первую строку с адресом."""
    address_lines = raw_text.split('\n')  # Разбиваем текст по строкам
    if len(address_lines) > 1:
        first_line = address_lines[0].strip()  # Берем только первую строку и удаляем лишние пробелы
        first_line += ', ' + address_lines[1].strip()
    else:
        first_line = address_lines[0].strip()
    return first_line

def iterate_pickup_points(driver):
    """Перебирает все доступные пункты выдачи и возвращает данные с лучшей ценой."""
    try:
        best_price = float('inf')
        best_pickup_point = ""

        # Открыть меню пунктов выдачи
        WebDriverWait(driver, 2).until(
            EC.element_to_be_clickable((By.ID, "hyperlocation-unified-dialog-anchor"))
        ).click()

        # Ожидаем появления всех элементов ПВЗ
        WebDriverWait(driver, 2).until(
            EC.presence_of_all_elements_located((By.XPATH, "//div[@aria-label='Выбрать адрес доставки']"))
        )

        # Получаем все элементы пунктов выдачи с текстом "Пункт выдачи" или "7 дней хранения"
        pickup_points = driver.find_elements(By.XPATH, "//div[@aria-label='Выбрать адрес доставки' and (contains(., 'Пункт выдачи') or contains(., '7 дней хранения'))]")

        for i in range(len(pickup_points)):
            try:
                # Повторный поиск элемента для предотвращения stale element reference exception
                pickup_points = driver.find_elements(By.XPATH, "//div[@aria-label='Выбрать адрес доставки' and (contains(., 'Пункт выдачи') or contains(., '7 дней хранения'))]")
                if i >= len(pickup_points):
                    continue
                
                point = pickup_points[i]

                # Извлечение текста адреса
                point_address_raw = point.text.strip()
                point_address = clean_pickup_point_address(point_address_raw)

                # Прокрутка к элементу и клик по нему с помощью JavaScript
                driver.execute_script("arguments[0].scrollIntoView();", point)
                time.sleep(1)  # Пауза для прокрутки

                # Используем JavaScript для клика по элементу
                driver.execute_script("arguments[0].click();", point)
                time.sleep(3)  # Ждем завершения действия

                # После клика по пункту самовывоза необходимо подождать обновления цены
                price = extract_price(driver)

                # Сравниваем текущую цену с лучшей ценой
                if price < best_price:
                    best_price = price
                    best_pickup_point = point_address

                # После каждого выбора пункта выдачи, нужно снова открыть меню
                WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.ID, "hyperlocation-unified-dialog-anchor"))
                ).click()
                time.sleep(2)  # Пауза для обновления страницы и повторного открытия меню

            except Exception as e:
                pass  # Можно добавить логгирование в случае отладки

        return best_price, best_pickup_point

    except Exception as e:
        return float('inf'), ""  # Возвращаем 'inf' и пустую строку в случае ошибки

def cleanup(temp_user_data_dir):
    """Очищает временные директории."""
    try:
        shutil.rmtree(temp_user_data_dir)
    except Exception as e:
        pass  # Можно добавить логгирование в случае отладки

def run_profile(profile, api_key):
    """Выполняет процесс парсинга для одного профиля GoLogin."""
    profile_id = profile['id']
    profile_name = profile['name']

    try:
        driver, gl, temp_user_data_dir = start_selenium_with_profile(profile_id, api_key)
        try:
            driver.get(SITE_URL)
            time.sleep(2)  # Ждем загрузки страницы

            # Перебираем пункты выдачи и извлекаем лучшую цену и пункт выдачи
            best_price, best_pickup_point = iterate_pickup_points(driver)

        except Exception as e:
            best_price, best_pickup_point = float('inf'), ""
        finally:
            # Закрытие ресурсов и очистка
            driver.quit()
            gl.stop()
            cleanup(temp_user_data_dir)

    except Exception as e:
        best_price, best_pickup_point = float('inf'), ""

    return {'profile_name': profile_name, 'best_price': best_price, 'best_pickup_point': best_pickup_point}

def run_profiles_sequentially(api_key, max_profiles=5):
    """Выполняет процесс парсинга последовательно по всем профилям GoLogin."""
    profiles_data = get_profiles(api_key, PROFILE_FOLDER)  # Указание папки профилей
    if profiles_data is None:
        return

    if 'profiles' in profiles_data:
        profiles = profiles_data['profiles']

        if max_profiles is not None:
            profiles = profiles[:max_profiles]

        profile_data = []  # Список для сохранения данных профилей, цен и ПВЗ

        for profile in profiles:
            result = run_profile(profile, api_key)
            profile_data.append(result)

        # Сортировка результатов по цене от самой дешевой до самой дорогой
        profile_data = sorted(profile_data, key=lambda x: x['best_price'])

        # Вывод результатов в виде таблицы
        print("\nParsing complete. Results (sorted by best price):")
        print("{:<30} {:<15} {:<30}".format('Profile Name', 'Best Price', 'Best Pickup Point'))
        print("-" * 75)
        for data in profile_data:
            print("{:<30} {:<15} {:<30}".format(data['profile_name'], data['best_price'], data['best_pickup_point']))

    else:
        print("Unexpected response structure:", profiles_data)
        return

def main():
    """Основная точка входа в программу."""
    max_profiles_to_use = MAX_WORKERS  # Используем значение из конфигурации
    run_profiles_sequentially(API_KEY, max_profiles=max_profiles_to_use)

if __name__ == "__main__":
    main()
