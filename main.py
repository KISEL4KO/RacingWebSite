from flask import Flask, render_template
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import random
import pickle
import os

# Кэширование для уменьшения запросов
def cache_data(func, cache_time=3600):  # 1 час по умолчанию
    """Декоратор для кэширования данных"""
    cache_file = f'cache_{func.__name__}.pkl'

    def wrapper(*args, **kwargs):
        # Проверяем кэш
        if os.path.exists(cache_file):
            file_age = time.time() - os.path.getmtime(cache_file)
            if file_age < cache_time:
                with open(cache_file, 'rb') as f:
                    return pickle.load(f)

        # Получаем свежие данные
        result = func(*args, **kwargs)

        # Сохраняем в кэш
        if result:
            with open(cache_file, 'wb') as f:
                pickle.dump(result, f)

        return result

    return wrapper

@cache_data
# Функция для получения новостей Формулы 1 с сайта sportrbc.ru
def f1_news():
    try:
        # Отправка GET-запроса к странице с новостями Ф1
        r = requests.get('https://sportrbc.ru/formula1/', timeout=10)
        # Парсинг HTML-контента с помощью BeautifulSoup
        s = BeautifulSoup(r.text, 'lxml')

        # Поиск всех элементов span с классом 'normal-wrap' (заголовки новостей)
        span_elements = s.find_all('span', class_='normal-wrap')

        # Извлечение текста из каждого найденного span элемента
        # strip=True удаляет лишние пробелы в начале и конце строки
        titles = [span.get_text(strip=True) for span in span_elements]

        return titles  # Возвращаем список заголовков новостей
    except:
        return []  # Возвращаем пустой список в случае ошибки


@cache_data
# Функция для получения расписания Ф1 2025 с Википедии
def get_f1_schedule_wiki():
    """Получение расписания Ф1 2025 с Википедии"""

    url = 'https://en.wikipedia.org/wiki/2026_Formula_One_World_Championship'

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, 'lxml')
        tables = soup.find_all('table', class_='wikitable')

        if not tables:
            print("❌ Таблицы не найдены")
            return []

        # Ищем таблицу расписания
        schedule_table = None
        for table in tables:
            headers = table.find_all('th')
            header_texts = [h.get_text(strip=True) for h in headers]
            if any(keyword in ' '.join(header_texts) for keyword in ['Round', 'Gran Prix', 'Circuit']):
                schedule_table = table
                break

        if not schedule_table:
            schedule_table = tables[0]

        # Парсим данные
        schedule = []
        rows = schedule_table.find_all('tr')[1:]  # Пропускаем заголовок

        for row in rows:
            cols = row.find_all(['td', 'th'])
            if len(cols) >= 4:
                # Очищаем текст
                clean_cols = []
                for col in cols:
                    for sup in col.find_all('sup'):
                        sup.decompose()
                    for span in col.find_all('span', class_='noprint'):
                        span.decompose()
                    clean_text = col.get_text(' ', strip=True)
                    clean_cols.append(clean_text)

                race = {
                    'round': clean_cols[0] if len(clean_cols) > 0 else '',
                    'gp': clean_cols[1] if len(clean_cols) > 1 else '',
                    'circuit': clean_cols[2] if len(clean_cols) > 2 else '',
                    'date': clean_cols[3] if len(clean_cols) > 3 else '',
                }
                schedule.append(race)

        return schedule

    except Exception as e:
        print(f"❌ Ошибка при парсинге расписания: {e}")
        return []
@cache_data
def get_last_race_results():
    """Получение результатов последней гонки Ф1 2025"""

    url = 'https://en.wikipedia.org/wiki/2025_Formula_One_World_Championship'

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, 'lxml')

        # Ищем таблицу с результатами чемпионата
        tables = soup.find_all('table', class_='wikitable')

        if not tables:
            print("❌ Таблицы не найдены")
            return []

        # Ищем таблицу с заголовками гонок (должна быть таблица с флагами)
        results_table = None
        for table in tables:
            headers = table.find_all('th')
            if len(headers) > 15:  # Таблица чемпионата имеет много столбцов
                # Проверяем наличие заголовков гонок
                header_texts = [h.get_text(strip=True) for h in headers]
                if any('AUS' in text or 'CHN' in text or 'ABU' in text for text in header_texts):
                    results_table = table
                    break

        if not results_table:
            results_table = tables[1] if len(tables) > 1 else tables[0]

        # Определяем последнюю гонку по столбцам
        columns = results_table.find_all('tr')[0].find_all('th')

        # Находим индекс последнего столбца с результатами гонки (не Points)
        last_race_col_index = -2  # Предпоследний столбец (последний - Points)

        # Получаем название последней гонки из заголовка
        last_race_header = columns[last_race_col_index] if len(columns) > abs(last_race_col_index) else None
        last_race_name = "Последняя гонка"

        if last_race_header:
            # Пытаемся извлечь название гонки
            links = last_race_header.find_all('a')
            if links:
                last_race_name = links[0].get('title', '').replace('Grand Prix', '').strip()
            else:
                last_race_name = last_race_header.get_text(strip=True)

        # Парсим результаты последней гонки
        results = []
        rows = results_table.find_all('tr')[1:]  # Пропускаем заголовок

        for row in rows:
            cols = row.find_all(['td', 'th'])
            if len(cols) > 3:  # Должно быть хотя бы позиция, пилот и результаты
                # Получаем позицию
                position = cols[0].get_text(strip=True)

                # Получаем имя пилота
                driver_cell = cols[1]
                driver_name = driver_cell.get_text(strip=True)

                # Удаляем флаг и ссылки для чистого имени
                for flag in driver_cell.find_all('span', class_='flagicon'):
                    flag.decompose()
                for a in driver_cell.find_all('a'):
                    a.replace_with(a.get_text())
                driver_name = driver_cell.get_text(strip=True)

                # Получаем результат в последней гонке
                result_cell = cols[last_race_col_index]
                result = result_cell.get_text(strip=True)

                # Очищаем результат от примечаний
                for sup in result_cell.find_all('sup'):
                    sup.decompose()
                clean_result = result_cell.get_text(strip=True)

                # Получаем очки
                points_cell = cols[-1] if len(cols) > 0 else None
                points = points_cell.get_text(strip=True) if points_cell else "0"

                results.append({
                    'position': position,
                    'driver': driver_name,
                    'last_race_result': clean_result,
                    'points': points
                })

        # Фильтруем только тех, кто участвовал в последней гонке
        race_results = []
        for result in results:
            last_result = result['last_race_result']
            # Проверяем, что это валидный результат гонки (не пустой и не тире)
            if last_result and last_result != '' and last_result != '–' and not last_result.startswith('DSQ'):
                try:
                    # Пробуем преобразовать в число (позиция)
                    int_position = int(last_result)
                    race_results.append(result)
                except:
                    # Если не число, проверяем на спец. статусы
                    if last_result in ['Ret', 'DNS', 'WD'] or '†' in last_result:
                        race_results.append(result)

        return {
            'race_name': last_race_name,
            'results': sorted(race_results, key=lambda x: (
                1000 if x['last_race_result'] in ['Ret', 'DNS', 'WD']
                else int(x['last_race_result'].replace('†', '')) if x['last_race_result'].replace('†', '').isdigit()
                else 999
            ))
        }

    except Exception as e:
        print(f"❌ Ошибка при парсинге результатов: {e}")
        return {'race_name': 'Ошибка', 'results': []}


# Функция для получения ID последнего видео/трансляции Формулы 1 с Rutube
def f1_watch():
    try:
        channel_id = 34418531  # ID канала Формулы 1 на Rutube
        # Формирование URL для API Rutube
        url = f"https://rutube.ru/api/video/person/{channel_id}/"

        # Отправка запроса к API Rutube
        response = requests.get(url, timeout=10)
        # Преобразование ответа в формат JSON
        videos_data = response.json()
        # Возвращаем ID второго видео из результатов (индекс 1)
        # (предполагается, что первое видео может быть закрепленным или неактуальным)
        return videos_data['results'][1]['id']
    except:
        return None


# Функция для получения ID последнего видео WEC (FIA World Endurance Championship) с YouTube
def wec_watch():
    try:
        youtube_API_KEY = ""  # Ключ API YouTube
        # Формирование URL запроса к YouTube API
        # Параметры запроса:
        # - part=snippet: запрашиваем основную информацию о видео
        # - q=FIAWEC: поиск по запросу "FIAWEC"
        # - type=video: ищем только видео (не плейлисты или каналы)
        # - maxResults=10: получаем до 10 результатов
        # - order=date: сортируем по дате (самые новые первые)
        url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q=FIAWEC&type=video&maxResults=10&order=date&key={youtube_API_KEY}"

        response = requests.get(url, timeout=10)  # Отправка запроса
        data = response.json()  # Преобразование ответа в JSON

        l = []  # Создаем пустой список для хранения ID видео
        # Проходим по всем элементам в ответе
        for item in data['items']:
            # Добавляем только ID видео в список
            l.append(item['id']['videoId'])

        # Проверяем, есть ли результаты в списке
        if l:
            return l[1]  # Возвращаем ID второго видео (индекс 1)
        else:
            return None  # Если результатов нет, возвращаем None
    except:
        return None


# Функция для получения ID последнего видео/трансляции WRC (World Rally Championship) с Rutube
def wrc_watch():
    try:
        channel_id = 46309562  # ID канала WRC на Rutube
        # Формирование URL для API Rutube
        url = f"https://rutube.ru/api/video/person/{channel_id}/"

        response = requests.get(url, timeout=10)  # Отправка запроса
        videos_data = response.json()  # Преобразование ответа в JSON
        # Возвращаем ID второго видео из результатов
        return videos_data['results'][1]['id']
    except:
        return None


# Инициализация Flask приложения
app = Flask(__name__)


# Маршрут для главной страницы
@app.route("/")
@app.route("/home")
def index():
    return render_template("index.html")


# Маршрут для страницы "О нас"
@app.route("/about")
def about():
    return render_template("about.html")


# Маршрут для базового шаблона
@app.route("/base")
def base():
    return render_template("base.html")


# Маршрут для страницы Формулы 1
@app.route("/f1")
def f1():
    # Формирование URL для встраивания видео с Rutube
    video_id = f1_watch()
    url = f"https://rutube.ru/play/embed/{video_id}" if video_id else ""

    # Получаем новости и расписание
    news_list = f1_news()
    schedule_list = get_f1_schedule_wiki()

    # Получаем результаты последней гонки
    race_data = get_last_race_results()  # Это возвращает словарь с 'race_name' и 'results'

    # Передаем в шаблон как last_race_results
    return render_template("f1.html",
                           video=url,
                           news=news_list[:10] if news_list else [],
                           schedule=schedule_list[:8] if schedule_list else [],
                           last_race_results=race_data)  # Изменено с standings на last_race_results


# Маршрут для страницы WRC
@app.route("/wrc")
def wrc():
    video_id = wrc_watch()
    url = f"https://rutube.ru/play/embed/{video_id}" if video_id else ""
    return render_template("wrc.html", video=url)


# Маршрут для страницы WEC
@app.route("/wec")
def wec():
    video_id = wec_watch()
    url = f'https://www.youtube.com/embed/{video_id}' if video_id else ""
    return render_template("wec.html", video=url)


# Маршрут для отдельной страницы расписания
@app.route("/schedule")
def schedule():
    schedule_list = get_f1_schedule_wiki()
    return render_template("schedule.html", schedule=schedule_list)


# Точка входа в приложение
if __name__ == "__main__":
    # Запуск Flask приложения
    app.run(debug=True, host='0.0.0.0', port=5000)
