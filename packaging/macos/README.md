# macOS self-contained JAR release

These releases contain the application, CPython, and Tcl/Tk. End users need
only Java 21 or newer. Build one JAR per CPU architecture:

```sh
python3 scripts/build_macos_jar.py --arch arm64 \
  --runtime data/runtime/cpython-3.13.16+20261013-aarch64-apple-darwin-install_only.tar.gz \
  --output dist/LowYOutpostFinder-macos-arm64.jar

python3 scripts/build_macos_jar.py --arch x86_64 \
  --runtime data/runtime/cpython-3.13.16+20261013-x86_64-apple-darwin-install_only.tar.gz \
  --output dist/LowYOutpostFinder-macos-x86_64.jar
```

Verify the artifacts before release:

```sh
python3 scripts/verify_macos_jar.py dist/LowYOutpostFinder-macos-arm64.jar --arch arm64
python3 scripts/verify_macos_jar.py dist/LowYOutpostFinder-macos-x86_64.jar --arch x86_64
```

Runtime archives are never trusted by filename alone. The builder checks their
pinned SHA-256, CPU architecture, Python executable, `_tkinter`, Tcl/Tk data,
license file, path safety, and internal links before writing a JAR.
