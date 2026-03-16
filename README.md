# flashboot-core

A lightweight, Spring Boot-inspired framework for Python. Build structured, maintainable applications with dependency injection, event-driven architecture, environment profiles, and more.

## Installation

```bash
pip install flashboot-core
```

Requires Python >= 3.10.

## Quick Start

```python
from flashboot_core.beans.decorators import component
from flashboot_core.context.flash_app import FlashApplication

@component(name="greeter")
class Greeter:
    def hello(self, name: str) -> str:
        return f"Hello, {name}!"

app = FlashApplication(Greeter)
context = app.run()
```

## Features

### Component & Dependency Injection

Mark classes as components for auto-discovery and registration:

```python
from flashboot_core.beans.decorators import component
from flashboot_core.beans.lifecycle import post_construct, pre_destroy

@component(name="user_service")
class UserService:
    @post_construct
    def init(self):
        print("UserService initialized")

    @pre_destroy
    def cleanup(self):
        print("UserService destroyed")
```

### Application Context

Register and retrieve beans programmatically:

```python
from flashboot_core.context.app_context import ApplicationContext

context = ApplicationContext()
context.register_bean("user_service", UserService())

service = context.get_bean("user_service")
```

### Environment & Profiles

Manage configuration across `dev`, `test`, and `prod` environments:

```python
from flashboot_core.env import Environment

profiles = Environment.get_active_profiles(default_profile="dev")
# Set via env var: profiles.active=dev
# Or CLI arg:      --profiles.active=dev
```

Bind YAML configuration directly to classes:

```python
from flashboot_core.env import property_bind

@property_bind("database", config_dir="./resources/configs")
class DatabaseConfig:
    host: str
    port: int
    username: str

# Fields auto-populated from YAML:
# database:
#   host: localhost
#   port: 5432
#   username: admin
```

### Event Bus

Publish and subscribe to events with priority support:

```python
from flashboot_core.event_bus import sync_event_bus

@sync_event_bus.on("user_created", priority=10)
def send_welcome_email(user_id):
    print(f"Sending welcome email to user {user_id}")

@sync_event_bus.on("user_created", priority=1)
def log_user_creation(user_id):
    print(f"User {user_id} created")

# Higher priority executes first
sync_event_bus.emit("user_created", user_id=42)
```

### Project Root Detection

Smart project root discovery with monorepo support:

```python
from flashboot_core.utils.project_utils import (
    get_project_root,
    get_workspace_root,
    setup_import_path,
)

# Find the nearest project root (sub-project level)
project = get_project_root()

# Find the outermost workspace root (monorepo level)
workspace = get_workspace_root()

# Add project root to sys.path
setup_import_path()
```

Supports multiple search strategies: `.root` marker files, VCS (git/svn/hg), marker files (`pyproject.toml`, `setup.py`, etc.), and directory structure heuristics.

Place a `.root` file in any directory to explicitly mark it as a project root.

### File I/O

```python
from flashboot_core.io.file import File

f = File("/path/to/config.yaml")
content = f.read_text()
```

## Architecture

```
flashboot_core/
├── beans/          # Component registration & lifecycle
├── context/        # Application context & component scanning
├── env/            # Environment profiles & property binding
├── event_bus/      # Sync & async event pub/sub
├── aop/            # Aspect-oriented programming
├── resilience/     # Circuit breaker, retry, rate limiter, timeout
├── scheduling/     # Scheduled task execution
├── serialization/  # JSON/YAML serialization
├── data/           # Caching, transactions, repository pattern
├── io/             # File & resource abstractions
├── concurrent/     # Concurrency utilities
├── utils/          # Project root detection & helpers
├── logging/        # Logging configuration
├── testing/        # Test utilities
└── exceptions/     # Exception hierarchy
```

## Roadmap

- Async Event Bus
- AOP decorators
- Resilience patterns (retry, circuit breaker, rate limiter, timeout)
- Scheduled tasks
- Data access layer (repository pattern, transactions, caching)
- Serialization framework

## License

MIT
