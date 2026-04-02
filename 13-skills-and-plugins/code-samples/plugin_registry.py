"""
Built-in vs marketplace plugin records — typical host patterns.

- Built-ins: code-registered map; id = "{name}@builtin".
- Marketplace: path + manifest metadata; skills loaded from manifest paths in
  the real loader (here we only model registration).
"""

from __future__ import annotations

from dataclasses import dataclass, field


BUILTIN_MARKETPLACE = "builtin"


@dataclass(frozen=True)
class BuiltinPluginDefinition:
    name: str
    description: str
    version: str = "0.0.0"
    skill_names: tuple[str, ...] = ()
    default_enabled: bool = True


@dataclass
class BuiltinRegistry:
    _defs: dict[str, BuiltinPluginDefinition] = field(default_factory=dict)

    def register(self, d: BuiltinPluginDefinition) -> None:
        self._defs[d.name] = d

    def plugin_id(self, name: str) -> str:
        return f"{name}@{BUILTIN_MARKETPLACE}"

    def enabled_skills(
        self, user_toggles: dict[str, bool | None]
    ) -> list[str]:
        out: list[str] = []
        for name, d in self._defs.items():
            pid = self.plugin_id(name)
            pref = user_toggles.get(pid)
            is_on = d.default_enabled if pref is None else bool(pref)
            if is_on:
                out.extend(d.skill_names)
        return out


@dataclass(frozen=True)
class MarketplacePlugin:
    """Subset of LoadedPlugin fields relevant to docs."""

    name: str
    path: str
    manifest_version: str
    skills_path: str | None = None


if __name__ == "__main__":
    reg = BuiltinRegistry()
    reg.register(
        BuiltinPluginDefinition(
            name="demo",
            description="Demo built-in",
            skill_names=("demo-skill",),
            default_enabled=True,
        )
    )
    assert reg.plugin_id("demo") == "demo@builtin"
    assert reg.enabled_skills({}) == ["demo-skill"]
    assert reg.enabled_skills({"demo@builtin": False}) == []

    mp = MarketplacePlugin(
        name="acme-tools",
        path="/tmp/plugins/acme",
        manifest_version="1.2.0",
        skills_path="skills",
    )
    assert mp.skills_path == "skills"
    print("plugin_registry ok")
