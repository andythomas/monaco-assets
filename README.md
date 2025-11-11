# Monaco Editor Assets

A Python package that provides easy access to Monaco Editor assets. Assets are
automatically downloaded on first use, eliminating the need to bundle large
files with the package. The assets can be served by a webserver on a custom port.

## Installation

```bash
python3 -m pip install monaco-assets
# or
uv pip install monaco-assets
```

## Quick Start

```python
import monaco_assets
server = monaco_assets.MonacoServer(port=8000)
```

Now, you can use `http://localhost:8000/min/vs/loader.js` in a webbrowser to see, e.g., loader.js.
Please note that there are no directory listings, one has to directly address the file(s).

## Cache Management

```python
import monaco_assets

# Clear cache to free space before uninstalling the package
monaco_assets.clear_cache()
```

## Cache Locations

Assets are cached in platform-appropriate directories using the `platformdirs` library

## How It Works

1. **First Use**: When `get_path()` is called for the first time, the package:
   - Downloads Monaco Editor from npmjs.org
   - Verifies the download integrity with SHA1 hash
   - Extracts assets to the user cache directory
   - Returns the path to the assets

2. **Subsequent Uses**: The package checks the cache and returns the existing assets path
   immediately.

## Download Issues

If asset download fails:

1. Check internet connectivity
2. Verify firewall settings allow access to registry.npmjs.org
3. Check disk space in cache directory

## Cache Issues

Clear and re-download if corrupted.

```python
monaco_assets.clear_cache()
assets_path = monaco_assets.get_path()
```

## Version Correspondence

Version correspondence will be ensured after initial bugfixes.

| Package Version | Monaco Editor Version |
| --------------- | --------------------- |
| 0.5.1           | 0.54.0                |

## Requirements

- Python 3.10+
- Internet connection (only for initial asset download)
- ~100MB disk space for Monaco Editor assets

## License

MIT License - see [LICENSE](license.txt) file for details.

Monaco Editor is licensed under the MIT License by Microsoft Corporation.
