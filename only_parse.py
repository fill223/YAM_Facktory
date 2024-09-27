import os
import sys
import re
import time
import shutil
import logging
import requests
import configparser
from gologin import GoLogin
from selenium import webdriver
from contextlib import contextmanager
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from multiprocessing import Pool
from sys import platform

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Загрузка конфигурации из config.ini
config = configparser.ConfigParser()
config.read('config.ini')

# Чтение параметров из конфигурационного файла
API_KEY = config['gologin']['api_key']
SITE_URL = config['gologin']['site_url']
CHROME_DRIVER_PATH = config['selenium']['chrome_driver_path']
AMOUNT_OF_PROFILES = config.getint('selenium', 'amount_of_profiles')
MULTI_WORKERS = config.getint('selenium', 'multi_workers')  # Количество профилей для единовременной обработки
PROFILE_FOLDER = config['gologin']['profile_folder']
BASE_PORT = 3500  # Стартовый порт для профилей
BASE_URL = 'https://api.gologin.com/browser/v2'

# Контекстный менеджер для подавления вывода в консоль и stderr
@contextmanager
def suppress_output():
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        try:
            sys.stdout = devnull
            sys.stderr = devnull
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

def get_profiles(api_key, folder):
    """Получает список профилей из GoLogin с использованием предоставленного API ключа и указанной папки."""
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(f"{BASE_URL}?folder={folder}", headers=headers)
        response.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred: {http_err}")
        return None
    except Exception as err:
        logging.error(f"Other error occurred: {err}")
        return None

    return response.json()

def start_selenium_with_profile(profile_id, api_key, port):
    """Запускает Selenium WebDriver с указанным профилем GoLogin в headless режиме на указанном порту."""
    try:
        gl = GoLogin({
            "token": api_key,
            "profile_id": profile_id,
            "port": port,  # Используем порт для GoLogin
            "extra_params": {
                "autoHeadless": True  # Включаем headless режим через GoLogin API
            }
        })

        # Перенаправляем все выводы библиотеки
        with suppress_output():
            debugger_address = gl.start()

        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_experimental_option("debuggerAddress", debugger_address)

        temp_user_data_dir = os.path.join('C:\\TempProfiles', f"chrome_profile_{profile_id}")
        os.makedirs(temp_user_data_dir, exist_ok=True)
        chrome_options.add_argument(f"--user-data-dir={temp_user_data_dir}")

        service = ChromeService(executable_path=CHROME_DRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=chrome_options)

        return driver, gl, temp_user_data_dir

    except Exception as e:
        logging.error(f"Failed to start Selenium WebDriver for profile {profile_id}: {e}")
        raise

def extract_price(driver):
    """Извлекает цену с текущей страницы."""
    try:
        price_element = WebDriverWait(driver, 10, poll_frequency=0.2).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "h3[data-auto='snippet-price-current']"))
        )
        price = price_element.text.strip()
        price = re.sub(r'[^\d,]', '', price)
        price_float = float(price.replace(',', '.'))

        return price_float
    except Exception as e:
        logging.error(f"Failed to extract price: {e}")
        return float('inf')

def clean_pickup_point_address(raw_text):
    """Очищает текст пункта выдачи, оставляя только первую строку с адресом."""
    address_lines = raw_text.split('\n')
    if len(address_lines) > 1:
        first_line = address_lines[0].strip()
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
                pickup_points = driver.find_elements(By.XPATH, "//div[@aria-label='Выбрать адрес доставки' and (contains(., 'Пункт выдачи') or contains(., '7 дней хранения'))]")
                if i >= len(pickup_points):
                    continue

                point = pickup_points[i]
                point_address_raw = point.text.strip()
                point_address = clean_pickup_point_address(point_address_raw)

                driver.execute_script("arguments[0].scrollIntoView();", point)
                time.sleep(1)  # Пауза для прокрутки

                driver.execute_script("arguments[0].click();", point)
                time.sleep(3)

                price = extract_price(driver)

                if price < best_price:
                    best_price = price
                    best_pickup_point = point_address

                WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.ID, "hyperlocation-unified-dialog-anchor"))
                ).click()
                time.sleep(2)

            except Exception as e:
                pass

        return best_price, best_pickup_point

    except Exception as e:
        return float('inf'), ""

def cleanup(temp_user_data_dir):
    """Очищает временные директории."""
    try:
        shutil.rmtree(temp_user_data_dir)
        logging.info(f"Temporary profile directory {temp_user_data_dir} deleted successfully.")
    except Exception as e:
        logging.error(f"Failed to delete temporary profile directory {temp_user_data_dir}: {e}")

def run_profile(profile):
    """Выполняет процесс парсинга для одного профиля GoLogin с использованием уникального порта."""
    profile_id = profile['id']
    profile_name = profile['name']
    port = profile['port']

    logging.info(f"Открытие профиля {profile_name} на порту {port}...")

    try:
        with suppress_output():
            driver, gl, temp_user_data_dir = start_selenium_with_profile(profile_id, API_KEY, port)
        try:
            driver.get(SITE_URL)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )

            if not driver.window_handles:
                logging.error(f"Окно закрыто для профиля {profile_name}.")
                return {'profile_name': profile_name, 'best_price': float('inf'), 'best_pickup_point': ""}

            best_price, best_pickup_point = iterate_pickup_points(driver)
        except Exception as e:
            logging.error(f"Ошибка во время выполнения профиля {profile_name}: {e}")
            best_price, best_pickup_point = float('inf'), ""
        finally:
            if driver:
                driver.quit()
            gl.stop()
            cleanup(temp_user_data_dir)

    except Exception as e:
        logging.error(f"Ошибка при запуске профиля {profile_name}: {e}")
        best_price, best_pickup_point = float('inf'), ""

    return {'profile_name': profile_name, 'best_price': best_price, 'best_pickup_point': best_pickup_point}

def run_profiles_parallel():
    """Выполняет процесс парсинга параллельно для всех профилей."""
    profiles_data = get_profiles(API_KEY, PROFILE_FOLDER)
    if profiles_data is None or 'profiles' not in profiles_data:
        logging.error("Не удалось получить профили.")
        return

    profiles = profiles_data['profiles'][:AMOUNT_OF_PROFILES]

    # Назначаем уникальные порты для каждого профиля
    for index, profile in enumerate(profiles):
        profile['port'] = BASE_PORT + index

    all_results = []  # Сохраняем все результаты

    # Разделяем профили на группы по размеру `MULTI_WORKERS`
    for i in range(0, len(profiles), MULTI_WORKERS):
        batch_profiles = profiles[i:i + MULTI_WORKERS]

        with Pool(len(batch_profiles)) as p:
            results = p.map(run_profile, batch_profiles)
            all_results.extend(results)  # Добавляем результаты текущей группы

    # Обработка всех результатов после завершения всех групп
    logging.info("Парсинг завершен.")
    logging.info("\nРезультаты парсинга (сортированы по лучшей цене):")
    all_results = sorted(all_results, key=lambda x: x['best_price'])
    logging.info("{:<30} {:<15} {:<30}".format('Profile Name', 'Best Price', 'Best Pickup Point'))
    logging.info("-" * 75)
    for result in all_results:
        logging.info("{:<30} {:<15} {:<30}".format(result['profile_name'], result['best_price'], result['best_pickup_point']))

def main():
    try:
        logging.info(f"Запуск программы с обработкой {AMOUNT_OF_PROFILES} профилей...")
        run_profiles_parallel()
        logging.info("Парсинг завершен.")
    except Exception as e:
        logging.error(f"Ошибка в main: {e}")

if __name__ == "__main__":
    main()
