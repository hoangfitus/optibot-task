# OptiBot Article Scraper

A Python-based article scraper that fetches articles from OptiSigns knowledge base and uploads them to OpenAI vector stores with intelligent delta detection to only process new or updated content.

## 🚀 Features

- **Delta Detection**: Only processes new or updated articles
- **MD5 Hashing**: Efficient change detection using content hashes
- **Parallel Processing**: Fast uploads with ThreadPoolExecutor
- **Token Estimation**: Accurate chunk estimation using tiktoken
- **State Persistence**: JSON-based state tracking
- **Comprehensive Logging**: Detailed execution logs
- **Docker Support**: Containerized deployment ready

## 📋 Prerequisites

- Python 3.12+
- OpenAI API Key
- Docker (optional, for containerized execution)

## 🛠️ Local Setup

### 1. Clone the Repository

```bash
git clone https://github.com/hoangfitus/optibot-task.git
cd optibot-task
```

### 2. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your OpenAI API key
nano .env
```

Add your OpenAI API key to `.env`:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

## 🏃 Running Locally

### Option 1: Direct Python Execution

```bash
# Run the scraper
python main.py
```

### Option 2: Docker Execution

```bash
# Build Docker image
docker build -t scraper-uploader .

# Run with Docker
docker run --rm --env-file .env -v $(pwd)/data:/app/data scraper-uploader
```

## 📁 Project Structure

```
optibot-task/
├── main.py                 # Main orchestration script
├── scraper.py             # Article fetching and delta detection
├── uploader.py            # OpenAI vector store management
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container configuration
├── docker-compose.yml    # Docker Compose setup
├── app.yaml             # DigitalOcean App Platform config
├── .env.example         # Environment template
├── .dockerignore       # Docker ignore rules
├── data/               # State files and data
│   └── articles_state.json
└── articles/          # Downloaded article files

```

## 🔧 Configuration Options

### Environment Variables

| Variable         | Description    | Default | Required |
| ---------------- | -------------- | ------- | -------- |
| `OPENAI_API_KEY` | OpenAI API key | -       | ✅       |

### State File Structure

The scraper maintains state in `data/articles_state.json`:

```json
{
  "articles": {
    "article_id": {
      "hash": "md5_hash_of_content",
      "updated_at": "2025-07-20T10:30:00Z",
      "title": "Article Title"
    }
  },
  "last_run": "2025-07-20T10:30:00Z"
}
```

## 📈 Performance

- **Initial sync**: ~2-5 minutes for 50 articles
- **Delta runs**: ~10-30 seconds (no changes)
- **Incremental**: ~30-60 seconds (few changes)
- **Memory usage**: ~50-100MB
- **Storage**: ~1-2MB for state and articles
