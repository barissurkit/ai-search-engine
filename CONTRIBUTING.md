# Katkı Rehberi

Katkıda bulunmak istediğiniz için teşekkürler!

## Kurulum

1. Repository'yi fork'layıp klonlayın.
2. Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js ve npm kurulu olmalıdır. Uygulamayı uçtan uca çalıştırmak için ayrıca Docker Compose, Ollama ve bir Tavily API anahtarı gerekir; ayrıntılar [docs/setup.md](docs/setup.md) dosyasındadır.
3. Bağımlılıkları kurun:

   ```sh
   cd backend && uv sync
   cd ../frontend && npm ci
   ```

## Testleri çalıştırma

Backend:

```sh
cd backend
uv run pytest
uv run ruff check .
```

Frontend:

```sh
cd frontend
npm run lint
npm run test:run
npm run build
```

Backend testleri API anahtarı olmadan çalışır (`.env` dosyası gerekmez).

## Pull request beklentileri

- `main` dalına doğrudan push yapmayın; ayrı bir dal açıp pull request gönderin.
- Pull request'i tek bir konuya odaklı tutun ve ne değiştiğini kısaca açıklayın.
- Davranış değiştiren her değişiklik için test ekleyin veya güncelleyin.
- Yukarıdaki komutlar yerelde geçmeli; GitHub Actions iş akışı (CI) yeşil olmalıdır.
- `.env` dosyalarını veya gerçek API anahtarlarını asla commit etmeyin.
