# Canventory

Pantry manager that tracks cans, soups and other food items with their quantities and expiration dates.
Sends email notification when some food is about to get wasted.

___

## Table of contents
- [Canventory](#canventory)
  - [Table of contents](#table-of-contents)
  - [Features](#features)
  - [Setup](#setup)
    - [Option 1: Docker](#option-1-docker)
      - [Prerequisites](#prerequisites)
    - [Option 2: Python venv](#option-2-python-venv)
      - [Prerequisites](#prerequisites-1)
      - [Installation](#installation)
  - [License](#license)

___

## Features
- **Status Filtering** - Click stat cards to filter by Fresh, Warning, Critical, or Expired
- **Image Support** - Upload and view pictures of items
- **User Administration** - Admin panel for managing users (first registered user becomes admin)
- **Email Notifications** - Optional SMTP integration

---

## Setup

### Option 1: Docker

#### Prerequisites
- Docker
- Docker Compose

```bash
# Clone the repository
git clone git@github.com:thamin-i/canventory.git
cd canventory

# Fill configuration file
cp .env.example .env
nano .env

# Build and start
docker-compose up --build

# Access the app
open http://localhost:8000
```

### Option 2: Python venv

#### Prerequisites
- Python 3.10 or higher
- pip (Python package manager)

#### Installation

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Fill configuration file
cp .env.example .env
nano .env

# Run the server
uvicorn app.main:APPLICATION --reload --host 0.0.0.0 --port 8000
```

---

## License

MIT License - Feel free to use and modify for your needs.
