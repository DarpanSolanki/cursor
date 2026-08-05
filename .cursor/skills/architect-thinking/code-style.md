<!-- Relocated verbatim from .cursor/rules/architect-thinking.mdc. Edit skill topics; thin architect-thinking.md only routes here. -->

# Code style: concise and crisp

concise and crisp

When writing or editing code in this project:

- **Default to concise**: Prefer fewer lines, minimal helpers, and no unnecessary repetition. Write the compact version first, not the verbose one.
- **Avoid verbosity**: Don't add extra methods, layers, or comments just for "clarity" when the same behavior can be expressed more briefly. One clear traversal beats multiple long methods when behavior is the same.
- **Crisp over elaborate**: Favor direct logic and reuse (e.g. one shared method with a few call sites) over sprawling, step-by-step code unless the user explicitly asks for more detail or documentation.

You do not need the user to say "keep it concise" each time—apply this by default.

---

