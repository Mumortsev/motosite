# МОТО-АЛЬЯНС КУБАНЬ

Проект развёрнут из `motosite-code.zip`. Предыдущий HTML заменён `index.html` из архива; изображения находятся в `images/`. Исходный архив сохранён.

## GitHub Pages — статическая демонстрация

В Settings → Pages выберите Source: GitHub Actions. Затем запустите workflow **Deploy Moto Alliance demo to GitHub Pages** из Actions. Ожидаемый URL: https://mumortsev.github.io/motosite/

Workflow публикует только `index.html`, `images/` и `.nojekyll`. Сервер, архив и настройки окружения в публичную сборку не входят. В приватном репозитории доступность Pages зависит от тарифа GitHub.

На Pages доступны интерфейс, готовые диагностические карточки, калькулятор и карта при доступности внешних сервисов. Индивидуальный ИИ-разбор отключён и явно помечен: Pages не исполняет Python.

Локальный просмотр этой же демоверсии:

```sh
python -m http.server 8080
```

Откройте http://localhost:8080/?demo=1

## Python-сервер / Amvera

В архиве сохранены `server.py`, `Dockerfile`, `amvera.yml`, `system_prompt.txt` и `start.bat`. Для реального ИИ-разбора задайте `DEEPINFRA_API_KEY` в окружении сервера, при необходимости `DEEPINFRA_MODEL` и `PORT`. Не помещайте действующие ключи в Git или публичные файлы. `.env.example` содержит только шаблон.

```sh
PORT=8080 python server.py
```

Откройте http://localhost:8080/ без параметра `demo`. Вызов DeepInfra требует действительного ключа и доступа к API; публикация на Pages его не подключает.
