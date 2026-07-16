# Project Structure

This document outlines the organization of the project source code.

## Overview
The project is organized into a "Core" layer (independent logic) and a "Bot" layer (Discord-specific implementation). This separation ensures that core features like AI inference and database management can be maintained or swapped independently of the Discord interface.

## Directory Structure

### `src/`
- **`clanker.py`**: The primary entry point for the application. Initializes configuration, database connections, and starts the Discord bot.
- **`config.py`**: Handles environment variables and global constants.

### `src/core/` (Core Logic)
This directory contains logic that is agnostic of the delivery platform.
- **`ai/`**: 
    - `client.py`: Manages interaction with `ollama`.
- **`tools/`**: 
    - `tool_router.py`: Routing and configuration for tools available to the LLM
    - `other`: Tool implementation
- **`db/`**: 
    - `manager.py`: Handles database connections and session management.
    - `migrations.py`: Manages database migrations and initial setup.

### `src/bot/` (Discord Interface)
This directory contains code specific to the Discord integration.
- **`commands/`**: Organized command handlers (e.g., `admin.py`, `general.py`).
- **`events.py`**: Listens for and processes Discord events (e.g., `on_ready`, `on_message`).
- **`cogs/`**: Modular components for specific bot features.
- **`utils.py`**: Helper functions specifically for Discord objects like Embeds and Buttons.
