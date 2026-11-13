#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОТО-АЛЬЯНС КУБАНЬ — Production HTTP-сервер для Amvera / Docker
Порт: 80
Поддержка DeepInfra / DeepSeek с кэшированием
"""

import http.server
import socketserver
import json
import urllib.request
import urllib.error
import os
import hashlib
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, '.env')
SYSTEM_PROMPT_PATH = os.path.join(BASE_DIR, 'system_prompt.txt')

def get_html_file():
    for name in ['index.html', 'gemini-code-1792671903411.html']:
        path = os.path.join(BASE_DIR, name)
        if os.path.exists(path):
            return path
    return os.path.join(BASE_DIR, 'index.html')

# 1. Чтение переменных окружения (Приоритет: Amvera os.environ -> .env -> defaults)
def load_env():
    env = {
        'DEEPINFRA_API_KEY': '',
        'DEEPINFRA_MODEL': 'deepseek-ai/DeepSeek-V4.1-Flash-1017',
        'CACHE_ENABLED': 'true',
        'PORT': '80'
    }

    # 1.1 Системные переменные окружения Amvera / Docker имеют высший приоритет
    for key in ['DEEPINFRA_API_KEY', 'DEEPINFRA_MODEL', 'CACHE_ENABLED', 'PORT']:
        val = os.environ.get(key)
        if val is not None and val.strip():
            env[key] = val.strip()

    # 1.2 Дочитываем .env если переменной нет в os.environ
    if os.path.exists(ENV_PATH):
        try:
            with open(ENV_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        k, v = line.split('=', 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if not env.get(k):
                            env[k] = v
        except Exception as e:
            print(f"[ENV WARN] Ошибка чтения .env: {e}")

    # В контейнере всегда слушаем порт 80
    if not env.get('PORT') or os.environ.get('PORT') == '80':
        env['PORT'] = '80'

    return env

# 2. Чтение системного промта
def load_system_prompt():
    if os.path.exists(SYSTEM_PROMPT_PATH):
        try:
            with open(SYSTEM_PROMPT_PATH, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception:
            pass
    return "Ты главный инженер мотомастерской. Отвечай строго валидным JSON с полями: code, riskClass, riskText, title, desc, service, time, price, advice."

# 3. Менеджер кэша
def get_cache_file():
    if os.path.exists('/data') and os.access('/data', os.W_OK):
        d = '/data/.cache'
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, 'ai_cache.json')
    local_dir = os.path.join(BASE_DIR, '.cache')
    os.makedirs(local_dir, exist_ok=True)
    return os.path.join(local_dir, 'ai_cache.json')

def load_cache():
    cache_file = get_cache_file()
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache_data):
    cache_file = get_cache_file()
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[CACHE ERROR] Не удалось сохранить кэш в {cache_file}: {e}")

# 4. HTTP Обработчик
class MotoServerHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        # Отдача главного HTML файла для корня и /index.html
        if self.path in ['/', '/index.html'] or self.path.startswith('/?'):
            html_path = get_html_file()
            if os.path.exists(html_path):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                with open(html_path, 'rb') as f:
                    self.wfile.write(f.read())
                return

        # API проверки статуса сервера и модели
        elif self.path == '/api/status':
            env = load_env()
            cache = load_cache()
            has_key = bool(env.get('DEEPINFRA_API_KEY')) and env.get('DEEPINFRA_API_KEY') != 'your_deepinfra_api_key_here'
            resp = {
                'configured': has_key,
                'model': env.get('DEEPINFRA_MODEL'),
                'port': env.get('PORT', '80'),
                'cached_items': len(cache),
                'cache_path': get_cache_file(),
                'status': 'ready'
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(resp, ensure_ascii=False).encode('utf-8'))
            return

        super().do_GET()

    def do_POST(self):
        if self.path == '/api/diagnose':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8', errors='ignore')

            try:
                data = json.loads(body)
            except Exception:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(b'{"error": "Invalid JSON"}')
                return

            query = data.get('query', '').strip()
            division = data.get('division', 'custom')
            mode = data.get('mode', 'defect')

            if not query:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(b'{"error": "Query is empty"}')
                return

            env = load_env()
            api_key = env.get('DEEPINFRA_API_KEY', '').strip()
            model = env.get('DEEPINFRA_MODEL', 'deepseek-ai/DeepSeek-V4.1-Flash-1017')
            cache_enabled = env.get('CACHE_ENABLED', 'true').lower() == 'true'

            system_prompt = load_system_prompt()

            # Формирование хэша кэша: sha256(division + mode + query + model)
            cache_key = hashlib.sha256(f"{division}:{mode}:{model}:{query.lower()}".encode('utf-8')).hexdigest()

            # 4.1 Проверка попадания в кэш
            if cache_enabled:
                cache = load_cache()
                if cache_key in cache:
                    cached_item = cache[cache_key]
                    cached_item['cached'] = True
                    cached_item['model'] = model
                    print(f"[CACHE HIT] Запрос «{query}» отдан мгновенно из кэша.")
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(json.dumps(cached_item, ensure_ascii=False).encode('utf-8'))
                    return

            # 4.2 Проверка наличия ключа API
            if not api_key or api_key == 'your_deepinfra_api_key_here':
                self.send_response(503)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": "API ключ не настроен.",
                    "code": "#CFG-KEY",
                    "riskClass": "risk-yellow",
                    "riskText": "Требуется ключ",
                    "title": "Интеграция ИИ ожидает настройки",
                    "desc": "Укажите DEEPINFRA_API_KEY в переменных окружения панели Amvera.",
                    "service": "Подключение DeepInfra API",
                    "time": "1 минута",
                    "price": "Бесплатно",
                    "advice": "Зайдите в панель Amvera -> Настройки -> Переменные и вставьте ваш ключ."
                }, ensure_ascii=False).encode('utf-8'))
                return

            # 4.3 Формирование промта для DeepSeek
            mode_names = {
                'defect': 'Инструментальная дефектовка и поиск неисправностей',
                'tuning': 'Программа спортивного/кастом тюнинга и модернизации',
                'maintenance': 'Регламентное техническое обслуживание (ТО)'
            }
            mode_desc = mode_names.get(mode, 'Техническая экспертиза')
            division_desc = 'Тяжелый кастом, чопперы, бобберы и моторы V-Twin (Harley-Davidson, Indian)' if division == 'custom' else 'Спортивный дивизион мотокросса и хард-эндуро 2Т / 4Т (KTM, Husqvarna, GasGas, WP)'

            user_content = f"Дивизион: {division_desc}\nТип операции: {mode_desc}\nЗапрос/симптом клиента: «{query}»\nСформируй техническую карточку по регламенту."

            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.2,
                "max_tokens": 800,
                "response_format": {"type": "json_object"}
            }

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "MotoKuban-Amvera-Production/1.0"
            }

            req = urllib.request.Request(
                "https://api.deepinfra.com/v1/openai/chat/completions",
                data=json.dumps(payload).encode('utf-8'),
                headers=headers,
                method='POST'
            )

            try:
                with urllib.request.urlopen(req, timeout=40) as response:
                    res_body = response.read().decode('utf-8')
                    res_json = json.loads(res_body)
                    content_text = res_json['choices'][0]['message']['content'].strip()

                    clean_text = re.sub(r'^```json\s*', '', content_text)
                    clean_text = re.sub(r'\s*```$', '', clean_text)
                    result_data = json.loads(clean_text)
                    result_data['cached'] = False
                    result_data['model'] = model

                    # Сохраняем в кэш
                    if cache_enabled:
                        cache = load_cache()
                        cache[cache_key] = result_data
                        save_cache(cache)
                        print(f"[CACHE SAVED] Ответ для «{query}» сохранен в кэш.")

                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(json.dumps(result_data, ensure_ascii=False).encode('utf-8'))
                    return

            except urllib.error.HTTPError as e:
                err_body = e.read().decode('utf-8', errors='ignore')
                print(f"[API ERROR] HTTP {e.code}: {err_body}")
                self.send_response(502)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"DeepInfra API error: {e.code}", "details": err_body}, ensure_ascii=False).encode('utf-8'))
                return
            except Exception as e:
                print(f"[API ERROR] Exception: {e}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}, ensure_ascii=False).encode('utf-8'))
                return

def run_server():
    env = load_env()
    # Строго порт 80 (или значение PORT из окружения)
    port = int(env.get('PORT', 80))
    os.chdir(BASE_DIR)

    http.server.ThreadingHTTPServer.allow_reuse_address = True
    print(f"Запуск на 0.0.0.0:{port}...")
    sys.stdout.flush()
    with http.server.ThreadingHTTPServer(("0.0.0.0", port), MotoServerHandler) as httpd:
        print("="*60)
        print("  МОТО-АЛЬЯНС КУБАНЬ // PRODUCTION СЕРВЕР ЗАПУЩЕН")
        print("="*60)
        print(f"  Хост:         0.0.0.0")
        print(f"  Порт:         {port}")
        print(f"  Модель ИИ:    {env.get('DEEPINFRA_MODEL')}")
        print(f"  API Ключ:     {'[OK: УКАЗАН]' if env.get('DEEPINFRA_API_KEY') and env.get('DEEPINFRA_API_KEY') != 'your_deepinfra_api_key_here' else '[НЕ УКАЗАН - задайте в переменных окружения Amvera]'}")
        print(f"  Кэширование:  {env.get('CACHE_ENABLED')} (Файл: {get_cache_file()})")
        print("="*60)
        sys.stdout.flush()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nСервер остановлен.")

if __name__ == '__main__':
    run_server()
