<img src="docs/banner.png" alt="Forge Gallery — przeglądarka outputów Stable Diffusion" width="100%">

# Forge Gallery

Lekka, samodzielna przeglądarka i menadżer plików dla outputów **Stable Diffusion / Forge**.  
Działa jako serwer HTTP napisany w czystym Pythonie — bez frameworków, bez bazy danych.

![Python](https://img.shields.io/badge/python-3.9%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green)

---

## Funkcje

- **Przeglądarka katalogów** — nawigacja po folderach z outputami, widok kafelkowy i listowy
- **Podgląd folderów** — miniatury ostatnich 5 zdjęć na karcie każdego katalogu
- **Lightbox** — pełnoekranowy podgląd z nawigacją klawiaturą (← →, Esc)
- **Pobieranie** — pojedynczych plików bezpośrednio z lightboxa
- **Zaznaczanie masowe** — checkbox na każdym zdjęciu, zaznaczanie zakresu `Shift+click`
- **Zaznacz wszystko** — jednym kliknięciem
- **Przenoszenie zdjęć** — masowe przenoszenie zaznaczonych zdjęć do wybranego folderu
- **Przenoszenie folderów** — przenoszenie całych katalogów między innymi katalogami
- **Tworzenie folderów** — nowy folder z poziomu galerii
- **Usuwanie** — masowe usuwanie zaznaczonych zdjęć z potwierdzeniem
- **Zmiana widoku** — przełącznik kafelki / lista zapamiętywany w `localStorage`
- **Logowanie** — prosta autoryzacja z sesją cookie (SHA-256, konfiguracja przez env)
- **Bez zależności** — wyłącznie biblioteka standardowa Pythona

---

## Wymagania

- Python 3.9+
- Serwer Linux (działa też lokalnie na Windows/macOS)

---

## Instalacja

### 1. Pobierz skrypt

```bash
wget https://raw.githubusercontent.com/bkleparski/forge-gallery/main/forge-gallery.py
```

### 2. Skonfiguruj zmienne środowiskowe

```bash
cp .env.example .env
```

Edytuj `.env`:

```env
FG_USERNAME=admin
FG_PASSWORD_HASH=<hash SHA-256 twojego hasła>
FG_OUTPUTS_DIR=/home/user/stable-diffusion-webui/outputs
FG_PORT=7861
```

Wygeneruj hash hasła:
```bash
python3 -c "import hashlib; print(hashlib.sha256(b'twoje-haslo').hexdigest())"
```

### 3. Uruchom

```bash
source .env && python3 forge-gallery.py
```

Galeria dostępna pod `http://localhost:7861`

---

## Uruchomienie jako usługa systemd (Linux)

```bash
# Skopiuj przykładowy plik usługi
cp forge-gallery.service.example ~/.config/systemd/user/forge-gallery.service

# Utwórz plik z env vars (nie dodawaj do git!)
cp .env.example ~/.env.forge-gallery
# uzupełnij wartości w ~/.env.forge-gallery

# Włącz i uruchom usługę
systemctl --user daemon-reload
systemctl --user enable forge-gallery.service
systemctl --user start forge-gallery.service
```

---

## Struktura katalogów

Aplikacja rekurencyjnie przegląda katalog `FG_OUTPUTS_DIR` i wyświetla jego zawartość.  
Pliki zdjęć są wyświetlane w galerii, podfoldery jako karty z miniaturami.

```
outputs/
├── 2024-01-15/
│   ├── portrait_001.png
│   └── portrait_002.webp
├── landscapes/
│   ├── sunset_01.jpg
│   └── ...
└── ...
```

---

## Bezpieczeństwo

- Hasło **nigdy** nie jest przechowywane wprost — tylko hash SHA-256
- Plik `.env` z hasłem jest wykluczony z git przez `.gitignore`
- Sesja oparta o losowy token `secrets.token_hex(32)` z cookie `HttpOnly; SameSite=Lax`
- Wszystkie ścieżki plików są weryfikowane relative do `OUTPUTS_DIR` (ochrona przed path traversal)
- Katalogi poza `OUTPUTS_DIR` są blokowane

---

## Konfiguracja przez Cloudflare Tunnel

Galeria nie obsługuje HTTPS samodzielnie. Zalecane jest wystawienie przez **Cloudflare Tunnel**:

```bash
cloudflared tunnel --url http://localhost:7861
```

---

## Licencja

MIT — możesz używać, modyfikować i dystrybuować dowolnie.
