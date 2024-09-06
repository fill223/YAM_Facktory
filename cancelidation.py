import os
import configparser
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from gologin import GoLogin
import shutil
import time

# Загрузка конфигурации из config.ini
config = configparser.ConfigParser()
config.read('config.ini')

# Чтение параметров из конфигурационного файла
API_KEY = config['gologin']['api_key']
SITE_URL = config['gologin']['profile_url']
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

def extract_cancelled_orders(driver):
    """Извлекает отмененные заказы на странице."""
    try:
        # Ожидание загрузки страницы и элементов на ней
        WebDriverWait(driver, 10, poll_frequency=0.2).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Поиск всех элементов h3 с текстом "Отменён"
        cancelled_orders = driver.find_elements(By.XPATH, "//h3[contains(text(), 'Отменён')]")

        # Если нашли элементы с текстом "Отменён", возвращаем их
        if cancelled_orders:
            return ["Отменён"] * len(cancelled_orders)  # Возвращаем список с найденными статусами
        else:
            return ["No cancelled orders found"]

    except Exception as e:
        print(f"Failed to extract order statuses: {e}")
        return ["Failed to extract order statuses"]

def cleanup(temp_user_data_dir):
    """Очищает временные директории."""
    try:
        shutil.rmtree(temp_user_data_dir)
    except Exception as e:
        pass  # Можно добавить логгирование в случае отладки

def run_profile(profile, api_key, cancelled_profiles):
    """Выполняет процесс парсинга для одного профиля GoLogin."""
    profile_id = profile['id']
    profile_name = profile['name']

    try:
        driver, gl, temp_user_data_dir = start_selenium_with_profile(profile_id, api_key)
        try:
            # Открываем страницу заказов
            driver.get(SITE_URL)
            time.sleep(2)  # Ждем загрузки страницы

            # Извлекаем статусы заказов с текущей страницы
            cancelled_orders = extract_cancelled_orders(driver)
            print(f"Profile: {profile_name}, Cancelled Orders: {', '.join(cancelled_orders)}")

            # Если нашли отмененные заказы, добавляем профиль в список
            if "Отменён" in cancelled_orders:
                cancelled_profiles.append(profile_name)

        except Exception as e:
            print(f"Error during page interaction for profile {profile_name}: {e}")
        finally:
            # Закрытие ресурсов и очистка
            driver.quit()
            gl.stop()
            cleanup(temp_user_data_dir)

    except Exception as e:
        print(f"Error setting up Selenium for profile {profile_name}: {e}")

def run_profiles_sequentially(api_key, max_profiles=5):
    """Выполняет процесс парсинга последовательно по всем профилям GoLogin."""
    profiles_data = get_profiles(api_key, PROFILE_FOLDER)  # Указание папки профилей
    if profiles_data is None:
        return

    if 'profiles' in profiles_data:
        profiles = profiles_data['profiles']

        if max_profiles is not None:
            profiles = profiles[:max_profiles]

        # Список для хранения профилей с отмененными заказами
        cancelled_profiles = []

        for profile in profiles:
            run_profile(profile, api_key, cancelled_profiles)

        # После выполнения всех профилей, выводим список профилей с отмененными заказами
        print("\nПрофили с отмененными заказами:")
        if cancelled_profiles:
            for cancelled_profile in cancelled_profiles:
                print(cancelled_profile)
        else:
            print("Отмененные заказы не найдены.")

def main():
    """Основная точка входа в программу."""
    max_profiles_to_use = MAX_WORKERS  # Используем значение из конфигурации
    run_profiles_sequentially(API_KEY, max_profiles=max_profiles_to_use)

if __name__ == "__main__":
    main()
