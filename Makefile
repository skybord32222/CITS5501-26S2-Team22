# Requirements:
#
# - curl, tar, and xz (for extracting the typst .tar.xz archive)
# - Assumes 64-bit Linux (amd64/x86_64).
#   If pandoc and typst are already on PATH, they are used
#   directly and nothing is downloaded.
#
# Notes:
#
# - PANDOC_VERSION and TYPST_VERSION pin the versions of these tools
#   if a download is needed. Bump them to pull a newer release.
# - We check whether pandoc and typst are already on PATH. If so, those are
#   used as-is. Otherwise we use .build/bin/pandoc and .build/bin/typst. TODO:
#   Downloads are cached under .build/downloads; no sudo is needed. TODO:
#
# Porting to other platforms:
#
# - macOS: change PANDOC_URL to a "-macOS" asset (a .pkg, so the
#   download/extract recipe would need to change), and TYPST_URL to
#   an "apple-darwin" .tar.xz asset (extraction stays the same).
# - Windows: pandoc ships a .zip/.msi, typst ships a .zip; both the
#   archive extension and extraction commands (tar -> unzip) would
#   need to change accordingly.

SHELL := /bin/bash

.DELETE_ON_ERROR:

REPORT := report

PANDOC_VERSION := 3.10.1
TYPST_VERSION  := 0.15.0

# Prefer tools on PATH; otherwise use user-writable project-local copies. TODO:
BIN_DIR := .build/bin
CACHE_DIR := .build/downloads

PANDOC := $(shell command -v pandoc 2>/dev/null)
ifeq ($(PANDOC),)
PANDOC := $(BIN_DIR)/pandoc
endif

TYPST := $(shell command -v typst 2>/dev/null)
ifeq ($(TYPST),)
TYPST := $(BIN_DIR)/typst
endif

PANDOC_DIST := pandoc-$(PANDOC_VERSION)-linux-amd64
# The archive filename includes the platform; its root directory does not. TODO:
PANDOC_ARCHIVE_DIR := pandoc-$(PANDOC_VERSION)
PANDOC_URL  := https://github.com/jgm/pandoc/releases/download/$(PANDOC_VERSION)/$(PANDOC_DIST).tar.gz

TYPST_DIST := typst-x86_64-unknown-linux-musl
TYPST_URL  := https://github.com/typst/typst/releases/download/v$(TYPST_VERSION)/$(TYPST_DIST).tar.xz

.PHONY: all clean

all: $(REPORT).pdf

$(REPORT).pdf: $(REPORT).md Makefile pdf-layout.typ pdf-metadata.yaml $(PANDOC) $(TYPST)
	"$(PANDOC)" --pdf-engine="$(TYPST)" --metadata-file=pdf-metadata.yaml --include-in-header=pdf-layout.typ -o "$@" "$<"

# Cache downloads so rebuilding does not require downloading them again. TODO:
$(CACHE_DIR)/$(PANDOC_DIST).tar.gz:
	mkdir -p "$(CACHE_DIR)"
	@echo "Downloading pandoc $(PANDOC_VERSION)..."
	curl -fL --retry 2 -o "$@" "$(PANDOC_URL)"

$(CACHE_DIR)/$(TYPST_DIST)-$(TYPST_VERSION).tar.xz:
	mkdir -p "$(CACHE_DIR)"
	@echo "Downloading typst $(TYPST_VERSION)..."
	curl -fL --retry 2 -o "$@" "$(TYPST_URL)"

# Extract only each executable, using the actual archive directory layout. TODO:
$(BIN_DIR)/pandoc: $(CACHE_DIR)/$(PANDOC_DIST).tar.gz
	mkdir -p "$(BIN_DIR)"
	tar -xzf "$<" -C "$(BIN_DIR)" --strip-components=2 --touch "$(PANDOC_ARCHIVE_DIR)/bin/pandoc"
	chmod +x "$@"

$(BIN_DIR)/typst: $(CACHE_DIR)/$(TYPST_DIST)-$(TYPST_VERSION).tar.xz
	mkdir -p "$(BIN_DIR)"
	tar -xJf "$<" -C "$(BIN_DIR)" --strip-components=1 --touch "$(TYPST_DIST)/typst"
	chmod +x "$@"

clean:
	rm -f $(REPORT).pdf
