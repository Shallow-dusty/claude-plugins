# shallow-local · Claude Code Plugin Marketplace

Personal marketplace for Claude Code plugins developed by [@Shallow-dusty](https://github.com/Shallow-dusty).

## Plugins

| Plugin | Description |
|---|---|
| **[scriptorium](./scriptorium/)** | Academic research toolkit — paper search (arXiv/bioRxiv/medRxiv/PubMed/Google Scholar), Zotero integration, LaTeX thesis build/wordcount/cross-ref check, LaTeX experiment tables, animation-rich HTML presentations. |
| **[trainhub](./trainhub/)** | Multi-platform ML training workflow — dispatch / monitor / harvest training jobs across Kaggle kernels, Google Colab, SSH remote GPU hosts. Project defaults persisted in `.trainhub.json`. |

## Installation

```bash
# Add this marketplace to Claude Code
claude plugin marketplace add https://github.com/Shallow-dusty/claude-plugins

# Install plugins
claude plugin install scriptorium@shallow-local
claude plugin install trainhub@shallow-local
```

Or locally (for development):

```bash
git clone https://github.com/Shallow-dusty/claude-plugins ~/.claude/plugins/local
claude plugin marketplace add ~/.claude/plugins/local
```

## Status

**0.1.0** — Early release, API may shift. Used daily by the author for thesis/research work.

## License

MIT
