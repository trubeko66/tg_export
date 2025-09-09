# Changelog

## v1.2.0 – Intelligent Media Download System

### 🚀 New Features
- Intelligent download system with adaptive load management
- Automatic Flood Wait protection with dynamic parameter changes
- File size caching for improved UI performance
- Extended error handling for various types of network issues

### 🔧 Fixes
- Zero-size file issue (replaced ThreadPoolExecutor with asyncio.gather)
- Event loop conflicts between threads during multi-threaded downloads
- Frequent API blocking "Sleeping for 4s on GetFileRequest"

### ⚡ Improvements
- Adaptive algorithms: automatic thread count changes (1-16) and delays (0.1-5.0s)
- Smart retries with exponential delays and jitter
- Batch file processing for better resource control
- Conservative start with 2 threads to prevent blocking

## v1.1.0 – WebDAV, Archives, Improved Channel Selection, Ad Filters

### 🚀 New Features
- WebDAV synchronization of channel lists and archives
- Import/export of channel lists to arbitrary JSON
- Configurable storage and export paths
- Improved channel selection with search and multi-select
- Ad and IT school promo filtering

### 🔧 Fixes
- Dataclass error with mutable default values
- Improved message filtering statistics

## v1.0.5 - KaTeX Error Fixes in Markdown Files

### 🔧 Fixes
- Fixed `KaTeX parse error: Undefined control sequence: \- at position 6`
- Resolved conflicts with KaTeX when processing symbols `\-`, `\+`, `\*`
- Improved LaTeX command handling in message text

### 🚀 New Features
- `_safe_markdown_text()` function for safe Markdown creation
- Minimal escaping of only critical symbols
- Automatic removal of potential LaTeX commands

## v1.0.4 - Channel Menu Navigation Fix

### 🔧 Fixes
- Fixed navigation command display (p/n/s/q) in channel selection menu
- Improved navigation menu readability
- Added warnings when trying to go beyond page boundaries

## v1.0.3 - Configuration Management System

### 🚀 New Features
- Automatic configuration saving to `.config.json`
- `ConfigManager` module for settings management
- Interactive configuration setup menu
- Separate `config.py` script for settings management

### ⚡ Improvements
- No need to enter settings on every launch
- Ability to change settings without restarting the program
- Settings validation on first launch

## v1.0.2 - Interface Improvements

### 🚀 New Features
- Paginated channel list display (10 channels per page)
- Channel page navigation
- Channel search by name and username

### 🔧 Fixes
- `'MessageReplies' object has no attribute 'get'` error
- Improved handling of various types of replies objects in Telegram API

## v1.0.1 - Syntax Error Fix

### 🔧 Fixes
- Fixed indentation error in line 349 of `telegram_exporter.py`
- Program now compiles and runs correctly

## v1.0.0 - Initial Version

### Features
- Telegram channel monitoring
- Export to JSON, HTML, Markdown formats
- Media file downloads
- Telegram bot notifications
- Daily scheduler for 00:00 checks
- Pseudographic interface
